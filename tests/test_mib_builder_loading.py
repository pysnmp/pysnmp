"""A MIB source MibBuilder refused to serve: the PEP 420 namespace package.

A plain directory of MIBs beside your script is one of these, which is what
made the refusal an everyday problem rather than an exotic one.
"""

import sys
import textwrap

import pytest

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
