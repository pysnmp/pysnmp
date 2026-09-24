"""Two ways MibBuilder used to fail to load a MIB without saying so.

One refused a source it should have served -- a PEP 420 namespace package, which
is what a plain directory of MIBs beside your script is. The other swallowed
"no such module" outright when no compiler was attached, and returned as though
the load had worked.
"""

import sys
import textwrap

import pytest

from pysnmp.smi import error
from pysnmp.smi.builder import DirMibSource, MibBuilder, ZipMibSource

#: A minimal generated MIB module, enough to load and export one symbol.
STUB_MIB = textwrap.dedent(
    """\
    (MibIdentifier,) = mibBuilder.importSymbols("SNMPv2-SMI", "MibIdentifier")
    stubObject = MibIdentifier((1, 3, 6, 1, 4, 1, 99999, 1))
    mibBuilder.exportSymbols("STUB-MIB", stubObject=stubObject)
    """
)


@pytest.fixture
def importableDir(tmp_path, monkeypatch):
    """Put a named directory of MIBs on sys.path, and take it back off after.

    Dropping the import cache on the way out matters as much as on the way in:
    sys.modules outlives monkeypatch's sys.path restoration, so a package left
    cached here would still resolve in a later test whose sys.path no longer
    has it -- which is a way to make a test pass or fail for reasons that have
    nothing to do with it.
    """

    placed = []

    def place(name):
        root = tmp_path / f"{name}-root"
        package = root / name
        package.mkdir(parents=True)
        (package / "STUB-MIB.py").write_text(STUB_MIB)

        monkeypatch.syspath_prepend(str(root))
        sys.modules.pop(name, None)
        placed.append(name)

        return package

    yield place

    for name in placed:
        sys.modules.pop(name, None)


@pytest.fixture
def namespacePackage(importableDir):
    """A directory of MIBs on sys.path with no ``__init__.py``."""
    return importableDir("stub_ns_mibs")


class TestNamespacePackageSource:
    """etingof/pysnmp#363: a bare directory refused as a MIB source."""

    def test_it_resolves_to_a_directory_source(self, namespacePackage):
        # A namespace package imports fine but has `__file__ is None`, so the
        # regular-package branch could not see it and it fell through to
        # "access error". Its directories are on
        # `__spec__.submodule_search_locations`, which nothing looked at.
        source = ZipMibSource("stub_ns_mibs").init()

        assert isinstance(source, DirMibSource)
        assert "STUB-MIB" in source.listdir()

    def test_a_mib_in_it_actually_loads(self, namespacePackage):
        built = MibBuilder()
        built.addMibSources(ZipMibSource("stub_ns_mibs"))
        built.loadModules("STUB-MIB")

        (stubObject,) = built.importSymbols("STUB-MIB", "stubObject")

        assert stubObject.name == (1, 3, 6, 1, 4, 1, 99999, 1)

    def test_the_source_keeps_its_kind_and_id(self, namespacePackage):
        # A substitute carries the original source's provenance: which kind of
        # thing serves a package is an installation detail.
        source = ZipMibSource("stub_ns_mibs").init()

        assert source.sourceId == "stub_ns_mibs"
        assert source.mibSourceKind == ZipMibSource("stub_ns_mibs").mibSourceKind

    def test_a_regular_package_still_resolves(self):
        # The branch added for namespace packages sits after this one, so the
        # ordinary case must be untouched.
        source = ZipMibSource("pysmi.mibs.pysnmp").init()

        assert "SNMPv2-MIB" in source.listdir()

    def test_a_bare_pysnmp_mibs_directory_no_longer_breaks_loading(self, importableDir):
        # The everyday case from the upstream report: MibBuilder's
        # DEFAULT_MISC_MIBS is "pysnmp_mibs", so someone keeping a plain
        # pysnmp_mibs/ folder of MIBs beside their script -- exactly what the
        # documentation's "drop your MIBs here" advice produces -- found that
        # MIB loading broke until they deleted the directory.
        importableDir("pysnmp_mibs")

        built = MibBuilder()
        built.loadModules("SNMPv2-MIB")

        assert "SNMPv2-MIB" in built.mibSymbols


class StubCompiler:
    """Stands in for a pysmi compiler, recording what it was asked to build."""

    def __init__(self, status):
        self.status = status
        self.compiled = []

    def compile(self, modName, **kwargs):
        self.compiled.append(modName)
        return {modName: self.status}


class TestMissingModuleIsReported:
    """etingof/pysnmp#5a1cb3ff: no compiler meant no error either."""

    def test_without_a_compiler_a_missing_module_raises(self):
        built = MibBuilder()

        with pytest.raises(error.MibNotFoundError) as raised:
            built.loadModules("NO-SUCH-MIB-AT-ALL")

        assert "NO-SUCH-MIB-AT-ALL" in str(raised.value)

    def test_without_a_compiler_nothing_is_silently_returned(self):
        # The shape of the defect: it returned `self`, so a caller chaining off
        # loadModules() saw success and got no module.
        built = MibBuilder()

        with pytest.raises(error.MibNotFoundError):
            built.loadModules("NO-SUCH-MIB-AT-ALL")

        assert "NO-SUCH-MIB-AT-ALL" not in built.mibSymbols

    def test_with_a_compiler_the_compile_is_still_attempted(self, tmp_path):
        # Behaviour with a compiler attached is unchanged: compile is tried,
        # and a compile that reports success is followed by a second load.
        built = MibBuilder()
        compiler = StubCompiler("compiled")
        built.setMibCompiler(compiler, str(tmp_path))

        with pytest.raises(error.MibNotFoundError):
            built.loadModules("NO-SUCH-MIB-AT-ALL")

        assert compiler.compiled == ["NO-SUCH-MIB-AT-ALL"]

    @pytest.mark.parametrize("status", ["failed", "missing"])
    def test_a_compile_failure_still_raises_with_its_diagnostics(
        self, tmp_path, status
    ):
        built = MibBuilder()
        built.setMibCompiler(StubCompiler(status), str(tmp_path))

        with pytest.raises(error.MibNotFoundError) as raised:
            built.loadModules("NO-SUCH-MIB-AT-ALL")

        assert "compilation error" in str(raised.value)

    def test_a_module_that_exists_still_loads(self):
        built = MibBuilder()
        built.loadModules("IF-MIB")

        assert "IF-MIB" in built.mibSymbols

    def test_several_names_load_together(self):
        built = MibBuilder()
        built.loadModules("IF-MIB", "SNMPv2-MIB")

        assert "IF-MIB" in built.mibSymbols
        assert "SNMPv2-MIB" in built.mibSymbols

    def test_one_missing_name_among_several_raises(self):
        built = MibBuilder()

        with pytest.raises(error.MibNotFoundError):
            built.loadModules("IF-MIB", "NO-SUCH-MIB-AT-ALL")

    def test_the_no_argument_form_is_unaffected(self):
        # The issue asked whether raising here makes `loadModules()` with no
        # names noisy, since that enumerates every source. It does not: those
        # names all came from listdir(), so they exist, and MibNotFoundError --
        # the only thing this change re-raises -- is not what that path hits.
        #
        # It does raise, from a bundled module whose dependency is missing, but
        # that is MibLoadError and predates this change; asserting the type
        # keeps the two apart if it is ever fixed.
        built = MibBuilder()

        try:
            built.loadModules()
        except error.MibNotFoundError:  # pragma: no cover - would be this change
            raise
        except error.MibLoadError:
            pass
