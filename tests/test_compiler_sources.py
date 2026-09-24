"""Where the compiler looks for ASN.1, and how the environment says so.

`PYSNMP_MIB_SOURCES` is the compile-side counterpart of `PYSNMP_MIB_DIRS` and
`PYSNMP_MIB_DBS`: generated `.py`, corpora, and now the ASN.1 a compiler renders
from. A container image can say where its MIBs are without inheriting two paths
from the host distribution that do not exist in it.

The awkward part is the separator. `os.pathsep` is a colon on POSIX, and a
colon is also what follows a URL scheme -- so a naive split turns one
``https://example.org/mibs`` into ``https`` and ``//example.org/mibs``, and
pysmi is handed a scheme it does not know plus a path that does not exist. That
is what most of this file is about.
"""

import os

import pytest

from pysnmp.smi.compiler import SOURCES_ENV, defaultSources, sourcesFromEnvironment

POSIX = os.pathsep == ":"


class TestUnset:
    """Unset has to stay distinguishable from set-to-nothing."""

    def test_unset_is_none(self):
        assert sourcesFromEnvironment(None) is None

    def test_empty_is_none_not_an_empty_list(self):
        """``PYSNMP_MIB_SOURCES=`` means nothing was said, not "compile from nowhere".

        An empty list would be a truthy-falsy trap in `addMibCompiler`, where
        the three-step fallback is ``sources= or environment or defaults``: a
        list that is empty falls through to the defaults anyway, and returning
        one would only make the intent harder to read.
        """
        assert sourcesFromEnvironment("") is None

    def test_nothing_but_separators_is_none(self):
        assert sourcesFromEnvironment(os.pathsep * 3) is None


class TestPaths:
    """The ordinary case: directories."""

    def test_one_directory(self):
        assert sourcesFromEnvironment("/mibs") == ["/mibs"]

    def test_order_is_kept(self):
        value = os.pathsep.join(("/first", "/second", "/third"))

        assert sourcesFromEnvironment(value) == ["/first", "/second", "/third"]

    def test_empty_entries_are_dropped(self):
        value = os.pathsep.join(("", "/mibs", "", "/more", ""))

        assert sourcesFromEnvironment(value) == ["/mibs", "/more"]

    def test_a_relative_path_is_left_alone(self):
        """pysmi's reader factory takes a bare path as a local one.

        Resolving it here would mean guessing what it is relative to, and the
        answer is the working directory of whatever process reads the variable
        -- which pysmi already applies.
        """
        assert sourcesFromEnvironment("mibs") == ["mibs"]


@pytest.mark.skipif(not POSIX, reason="os.pathsep is not a colon on this platform")
class TestUrlsOnPosix:
    """The colon that is a separator and the colon that is part of a URL."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.org/mibs",
            "https://example.org/mibs",
            "file:///usr/share/snmp/mibs",
            "zip://example.org/mibs.zip",
        ],
    )
    def test_a_url_survives_the_split(self, url):
        assert sourcesFromEnvironment(url) == [url]

    def test_a_url_beside_a_directory(self):
        value = os.pathsep.join(("https://example.org/mibs", "/mibs"))

        assert sourcesFromEnvironment(value) == [
            "https://example.org/mibs",
            "/mibs",
        ]

    def test_a_directory_beside_a_url(self):
        value = os.pathsep.join(("/mibs", "https://example.org/mibs"))

        assert sourcesFromEnvironment(value) == [
            "/mibs",
            "https://example.org/mibs",
        ]

    def test_two_urls(self):
        value = os.pathsep.join(
            ("https://example.org/mibs", "http://mirror.example.org/mibs")
        )

        assert sourcesFromEnvironment(value) == [
            "https://example.org/mibs",
            "http://mirror.example.org/mibs",
        ]

    def test_the_defaults_survive_a_round_trip(self):
        """The shipped defaults are `file://` URLs, so they are the case to check."""
        assert sourcesFromEnvironment(os.pathsep.join(defaultSources)) == list(
            defaultSources
        )

    def test_a_single_letter_is_not_a_scheme(self):
        """A Windows drive letter, which pysmi's reader factory takes as a path.

        Rejoining ``c`` with what follows would turn ``c:\\mibs`` into a URL
        with a one-character scheme, which is exactly the reading pysmi went
        out of its way to avoid.
        """
        value = os.pathsep.join(("c", "//mibs"))

        assert sourcesFromEnvironment(value) == ["c", "//mibs"]

    def test_a_bare_double_slash_is_not_glued_to_a_path(self):
        """Only a scheme is rejoined, and ``/mibs`` is not one."""
        value = os.pathsep.join(("/mibs", "//share/mibs"))

        assert sourcesFromEnvironment(value) == ["/mibs", "//share/mibs"]


class TestPrecedence:
    """Explicit beats environment beats default, and the environment is read late."""

    def test_the_environment_is_read_when_no_value_is_passed(self, monkeypatch):
        monkeypatch.setenv(SOURCES_ENV, "/from-the-environment")

        assert sourcesFromEnvironment() == ["/from-the-environment"]

    def test_an_unset_environment_reads_as_none(self, monkeypatch):
        monkeypatch.delenv(SOURCES_ENV, raising=False)

        assert sourcesFromEnvironment() is None

    def test_it_replaces_the_defaults_rather_than_adding_to_them(self, monkeypatch):
        """The rule `PYSNMP_MIB_DIRS` already follows.

        An image that states where its MIBs are should not also be searching
        two host paths that do not exist in it -- and a deployment that wants
        both can say both, which it cannot do the other way round.
        """
        monkeypatch.setenv(SOURCES_ENV, "/only-here")

        found = sourcesFromEnvironment()

        assert found == ["/only-here"]
        assert not set(found) & set(defaultSources)


class TestReachesTheCompiler:
    """The variable is worth nothing if `addMibCompiler` does not read it."""

    def _readers(self, mibBuilder):
        """What the attached compiler will actually read from, as strings.

        pysmi's readers have no public accessor and their ``str`` carries the
        path, which is all this needs -- the question is whether the directory
        arrived, not what class wraps it. (``repr`` does not: it is the default
        object one.)
        """
        compiler = mibBuilder.getMibCompiler()

        return [str(x) for x in compiler._sources]

    def test_the_environment_directory_is_searched(self, monkeypatch, tmp_path):
        from pysnmp.smi.builder import MibBuilder
        from pysnmp.smi.compiler import addMibCompiler

        directory = tmp_path / "asn1"
        directory.mkdir()
        monkeypatch.setenv(SOURCES_ENV, str(directory))

        builder = MibBuilder()
        addMibCompiler(builder)

        assert any(str(directory) in x for x in self._readers(builder))

    def test_an_explicit_argument_wins(self, monkeypatch, tmp_path):
        """A caller who passed ``sources=`` meant it.

        The environment is how a deployment states a default; an argument is a
        program stating a requirement, and the two disagreeing means the
        program is right.
        """
        from pysnmp.smi.builder import MibBuilder
        from pysnmp.smi.compiler import addMibCompiler

        fromEnv = tmp_path / "environment"
        fromArg = tmp_path / "argument"
        fromEnv.mkdir()
        fromArg.mkdir()

        monkeypatch.setenv(SOURCES_ENV, str(fromEnv))

        builder = MibBuilder()
        addMibCompiler(builder, sources=[str(fromArg)])

        readers = self._readers(builder)

        assert any(str(fromArg) in x for x in readers)
        assert not any(str(fromEnv) in x for x in readers)

    def test_unset_leaves_the_shipped_defaults(self, monkeypatch):
        from pysnmp.smi.builder import MibBuilder
        from pysnmp.smi.compiler import addMibCompiler

        monkeypatch.delenv(SOURCES_ENV, raising=False)

        builder = MibBuilder()
        addMibCompiler(builder)

        readers = self._readers(builder)

        assert len(readers) == len(defaultSources)
