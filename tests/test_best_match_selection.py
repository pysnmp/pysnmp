"""Which copy of a module wins when more than one source has it.

Source order does not decide. Two sources offering a module are offering the
same specification at two revisions, and the newer one is the answer wherever
it is found -- so the newest MODULE-IDENTITY revision wins and source order
only breaks the tie.

The distinction that matters: registering an *older* copy of a module must not
change what pysnmp resolves. Precedence by position would make that a silent
downgrade, which is the failure this rule exists to prevent.

pysmi states the revision as `PYSNMP_MODULE_REVISION` in every generated module
that has a MODULE-IDENTITY (pysnmp/pysmi#205), and `builder.revisionOf` reads it
off the compiled module without running it. See pysnmp/pysnmp#198.
"""

import warnings

import pytest

from pysnmp.smi import builder

NEWER = "200210160000Z"
OLDER = "199511090000Z"


def write(directory, name, revision, marker):
    """A minimal generated module: states a revision, exports a probe.

    ``PYSNMP_MODULE_ID`` is the one export name `exportSymbols` does not call
    `getLabel()` on, so the probe can be a plain string.
    """
    lines = []
    if revision is not None:
        lines.append(f"PYSNMP_MODULE_REVISION = {revision!r}")
    lines.append(f"mibBuilder.exportSymbols({name!r}, PYSNMP_MODULE_ID={marker!r})")
    path = directory / f"{name}.py"
    path.write_text("\n".join(lines) + "\n")

    return path


def resolve(name, *directories):
    """Load *name* with only *directories* as sources, in that order."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        mibBuilder = builder.MibBuilder()
        mibBuilder.setMibSources(
            *[builder.DirMibSource(str(d)).init() for d in directories]
        )
        mibBuilder.loadModules(name)

        return mibBuilder.mibSymbols[name]["PYSNMP_MODULE_ID"]


@pytest.fixture
def two(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    return first, second


class TestNewestRevisionWins:
    def test_the_newer_copy_wins_from_the_last_source(self, two):
        first, second = two
        write(first, "TEST-MIB", OLDER, "older")
        write(second, "TEST-MIB", NEWER, "newer")

        assert resolve("TEST-MIB", first, second) == "newer"

    def test_the_newer_copy_wins_from_the_first_source(self, two):
        """The same rule, with the sources the other way round."""
        first, second = two
        write(first, "TEST-MIB", NEWER, "newer")
        write(second, "TEST-MIB", OLDER, "older")

        assert resolve("TEST-MIB", first, second) == "newer"

    def test_registering_an_older_copy_does_not_change_the_answer(self, two):
        """The property the rule exists for.

        A caller who registers their own older copy of a module gets the newer
        one anyway. Under precedence by position they would silently get the
        downgrade.
        """
        first, second = two
        write(first, "TEST-MIB", NEWER, "newer")
        write(second, "TEST-MIB", OLDER, "older")

        assert resolve("TEST-MIB", second, first) == "newer"
        assert resolve("TEST-MIB", first, second) == "newer"

    def test_a_name_pysmi_does_not_bundle_is_decided_the_same_way(self, two):
        """No bundled-name gate, unlike `MibCompiler._candidate_sources`.

        pysmi restricts revision comparison to modules it ships a copy of, on
        the reasoning that two copies of a vendor module may be a collision
        rather than two revisions. Here every name found twice is compared.
        """
        first, second = two
        write(first, "ACME-WIDGET-MIB", OLDER, "older")
        write(second, "ACME-WIDGET-MIB", NEWER, "newer")

        assert resolve("ACME-WIDGET-MIB", first, second) == "newer"


class TestSourceOrderBreaksTies:
    def test_an_undated_candidate_leaves_it_to_source_order(self, two):
        """An undated copy cannot be placed against a dated one.

        This is the usual case for the SMI modules themselves, which carry no
        MODULE-IDENTITY at all.
        """
        first, second = two
        write(first, "TEST-MIB", None, "first")
        write(second, "TEST-MIB", NEWER, "dated")

        assert resolve("TEST-MIB", first, second) == "first"
        assert resolve("TEST-MIB", second, first) == "dated"

    def test_equal_revisions_leave_it_to_source_order(self, two):
        first, second = two
        write(first, "TEST-MIB", NEWER, "first")
        write(second, "TEST-MIB", NEWER, "second")

        assert resolve("TEST-MIB", first, second) == "first"
        assert resolve("TEST-MIB", second, first) == "second"

    def test_a_single_source_is_used_whatever_it_states(self, two):
        first, _ = two
        write(first, "TEST-MIB", None, "only")

        assert resolve("TEST-MIB", first) == "only"


class TestTheRevisionIsReadWithoutRunningTheModule:
    def test_a_losing_candidate_is_never_executed(self, tmp_path):
        """Reading a revision must not run the module.

        A pysnmp MIB registers its symbols as it runs, so executing every
        candidate to find out which to keep would load all of them. The loser
        here raises on execution: if it were run to be measured, this fails.
        """
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()

        (first / "TEST-MIB.py").write_text(
            f"PYSNMP_MODULE_REVISION = {OLDER!r}\n"
            "raise AssertionError('the losing candidate was executed')\n"
        )
        write(second, "TEST-MIB", NEWER, "newer")

        assert resolve("TEST-MIB", first, second) == "newer"

    def test_revision_of_reads_a_compiled_module(self, tmp_path):
        path = write(tmp_path, "TEST-MIB", NEWER, "probe")
        codeObj = compile(path.read_text(), str(path), "exec")

        assert builder.revisionOf(codeObj) == NEWER

    def test_revision_of_answers_none_without_the_constant(self, tmp_path):
        path = write(tmp_path, "TEST-MIB", None, "probe")
        codeObj = compile(path.read_text(), str(path), "exec")

        assert builder.revisionOf(codeObj) is None
