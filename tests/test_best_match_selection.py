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

import pathlib
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
    """Two source directories, to be searched in whatever order a test gives."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    return first, second


class TestNewestRevisionWins:
    def test_the_newer_copy_wins_from_the_last_source(self, two):
        """The arrangement first-source-wins got wrong."""
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
        """Nothing to choose between them, so the caller's order stands."""
        first, second = two
        write(first, "TEST-MIB", NEWER, "first")
        write(second, "TEST-MIB", NEWER, "second")

        assert resolve("TEST-MIB", first, second) == "first"
        assert resolve("TEST-MIB", second, first) == "second"

    def test_a_single_source_is_used_whatever_it_states(self, two):
        """One candidate is never compared against anything."""
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
        """Straight from the code object, which is what `read` returns."""
        path = write(tmp_path, "TEST-MIB", NEWER, "probe")
        codeObj = compile(path.read_text(), str(path), "exec")

        assert builder.revisionOf(codeObj) == NEWER

    def test_revision_of_answers_none_without_the_constant(self, tmp_path):
        """Absent is not an error: it means source order decides."""
        path = write(tmp_path, "TEST-MIB", None, "probe")
        codeObj = compile(path.read_text(), str(path), "exec")

        assert builder.revisionOf(codeObj) is None


class TestAnAlreadyLoadedModuleIsStable:
    """Selection decides what to load, not what to reload.

    Loading is not idempotent -- a MIB registers its symbols as it runs -- so
    executing a second copy over the first raises out of `exportSymbols` on the
    first symbol they share.

    Before selection stopped following source order this could not be reached:
    `addMibSources` appends, so the copy already loaded was still found first
    and the `modPathsSeen` check caught it. Best match puts a newer copy ahead
    of it, and a newer copy is a different path.
    """

    def test_adding_a_newer_source_does_not_disturb_a_loaded_module(self, two):
        first, second = two
        write(first, "TEST-MIB", OLDER, "older")
        write(second, "TEST-MIB", NEWER, "newer")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            mibBuilder = builder.MibBuilder()
            mibBuilder.setMibSources(builder.DirMibSource(str(first)).init())
            mibBuilder.loadModules("TEST-MIB")

            mibBuilder.addMibSources(builder.DirMibSource(str(second)))
            mibBuilder.loadModules("TEST-MIB")

        assert mibBuilder.mibSymbols["TEST-MIB"]["PYSNMP_MODULE_ID"] == "older"

    def test_unloading_first_picks_up_the_newer_copy(self, two):
        """The way to take a replacement, and it still selects by best match."""
        first, second = two
        write(first, "TEST-MIB", OLDER, "older")
        write(second, "TEST-MIB", NEWER, "newer")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            mibBuilder = builder.MibBuilder()
            mibBuilder.setMibSources(builder.DirMibSource(str(first)).init())
            mibBuilder.loadModules("TEST-MIB")

            mibBuilder.addMibSources(builder.DirMibSource(str(second)))
            mibBuilder.unloadModules("TEST-MIB")
            mibBuilder.loadModules("TEST-MIB")

        assert mibBuilder.mibSymbols["TEST-MIB"]["PYSNMP_MODULE_ID"] == "newer"


class TestAZipInstalledSourceReportsWhereItCameFrom:
    """`getModulePath` has to name a module a zip-imported package supplied.

    `ZipMibSource._init` rewrites `_srcName` to the archive member path --
    ``pysmi/mibs/pysnmp`` -- which names no file on disk and is ambiguous
    between two archives holding the same package. A wheel installs as a
    directory, so `_init` hands back a `DirMibSource` and nothing here is
    exercised by an ordinary install; a zip or egg install is what reaches it.
    """

    @staticmethod
    def _archive(tmp_path):
        """A zip holding one importable package with one MIB module in it."""
        import zipfile

        archive = tmp_path / "mibs.zip"
        module = (
            f"PYSNMP_MODULE_REVISION = {NEWER!r}\n"
            "mibBuilder.exportSymbols('ZIP-MIB', PYSNMP_MODULE_ID='from-zip')\n"
        )
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("zipped/__init__.py", "")
            zf.writestr("zipped/mibs/__init__.py", "")
            zf.writestr("zipped/mibs/ZIP-MIB.py", module)

        return archive

    def test_the_path_names_the_archive_it_came_from(self, tmp_path, monkeypatch):
        import importlib
        import importlib.util

        archive = self._archive(tmp_path)
        monkeypatch.syspath_prepend(str(archive))
        importlib.invalidate_caches()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            mibBuilder = builder.MibBuilder()
            mibBuilder.setMibSources(builder.ZipMibSource("zipped.mibs").init())
            mibBuilder.loadModules("ZIP-MIB")

        assert mibBuilder.mibSymbols["ZIP-MIB"]["PYSNMP_MODULE_ID"] == "from-zip"

        origin = pathlib.Path(mibBuilder.getModulePath("ZIP-MIB"))
        package = importlib.util.find_spec("zipped.mibs").submodule_search_locations[0]

        assert str(origin.parent) == package
        assert str(archive) in str(origin)
