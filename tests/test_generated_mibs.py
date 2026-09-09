"""pysnmp's own MIB modules still match the ASN.1 that defines them.

``PYSNMP-MIB``, ``PYSNMP-SOURCE-MIB`` and ``PYSNMP-USM-MIB`` are pysnmp's to
publish. The ASN.1 in ``docs/mibs`` defines them and the Python in
``pysnmp/smi/mibs`` renders it, so the two can disagree -- and did, for eight
years. The 2017 rendering had ``pysnmpUsmSecretAuthKey`` and five sibling
columns readable when their ASN.1 says ``not-accessible``, and carried a
``DEFVAL`` on each that no clause in the module asks for.

So the rendering is checked rather than trusted: re-render, and compare. What
a relation the ASN.1 cannot state looks like now is a file in
``pysnmp/smi/mibs/behavior/``, which this does not touch.
"""

import os

import pytest

from pysnmp.smi.builder import MibBuilder
from tools.regenerate_mibs import ASN1_DIR, MODULES, OUTPUT_DIR, build


@pytest.fixture(scope="module")
def rendered():
    """Every module rendered from its ASN.1, keyed by path."""
    return build()


@pytest.fixture(scope="module")
def builder():
    """A builder with pysnmp's own modules loaded."""
    built = MibBuilder()
    built.loadModules(*MODULES)

    return built


@pytest.mark.parametrize("module", MODULES)
def test_the_committed_module_matches_its_asn1(rendered, module):
    path = os.path.join(OUTPUT_DIR, f"{module}.py")

    with open(path, encoding="utf-8") as fileObj:
        committed = fileObj.read()

    assert committed == rendered[path], (
        f"{module}.py no longer matches {module}.txt. "
        f"Run: python tools/regenerate_mibs.py"
    )


@pytest.mark.parametrize("module", MODULES)
def test_the_asn1_source_is_present(module):
    assert os.path.exists(os.path.join(ASN1_DIR, f"{module}.txt"))


@pytest.mark.parametrize("module", MODULES)
def test_the_module_states_a_revision(builder, module):
    # A module that states no revision cannot be placed against another copy
    # of itself, so MibBuilder._candidates falls back to source order. The
    # 2017 renderings stated none.
    with open(os.path.join(OUTPUT_DIR, f"{module}.py"), encoding="utf-8") as fileObj:
        assert "PYSNMP_MODULE_REVISION" in fileObj.read()


@pytest.mark.parametrize("module", MODULES)
def test_the_module_loads_and_exports_its_identity(builder, module):
    assert "PYSNMP_MODULE_ID" in builder.mibSymbols[module]


class TestUsmSecretAccess:
    """The access correction the re-rendering carried, stated on its own.

    RFC 2578 section 7.3 and the module's own MAX-ACCESS clauses: the columns
    holding a user's pass-phrases are ``not-accessible``. The 2017 rendering
    left them at ``MibTableColumn``'s ``readonly`` default, which made every
    stored authentication and privacy pass-phrase readable over SNMP by anyone
    the view policy let reach the table.
    """

    SECRET_COLUMNS = (
        "pysnmpUsmSecretUserName",
        "pysnmpUsmSecretAuthKey",
        "pysnmpUsmSecretPrivKey",
        "pysnmpUsmKeyAuthLocalized",
        "pysnmpUsmKeyPrivLocalized",
        "pysnmpUsmKeyAuth",
        "pysnmpUsmKeyPriv",
    )

    @pytest.mark.parametrize("column", SECRET_COLUMNS)
    def test_secret_columns_are_not_readable(self, builder, column):
        (symbol,) = builder.importSymbols("PYSNMP-USM-MIB", column)

        assert symbol.maxAccess not in ("readonly", "readwrite", "readcreate")

    def test_the_row_status_column_stays_writable(self, builder):
        (status,) = builder.importSymbols("PYSNMP-USM-MIB", "pysnmpUsmSecretStatus")

        assert status.maxAccess == "readcreate"
