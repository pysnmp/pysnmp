"""The MIB modules pysnmp ships still match the ASN.1 that defines them.

Two sets, checked the same way for different reasons.

``PYSNMP-MIB``, ``PYSNMP-SOURCE-MIB`` and ``PYSNMP-USM-MIB`` are pysnmp's to
publish. The ASN.1 in ``docs/mibs`` defines them and the Python in
``pysnmp/smi/mibs`` renders it, so the two can disagree -- and did, for eight
years. The 2017 rendering had ``pysnmpUsmSecretAuthKey`` and five sibling
columns readable when their ASN.1 says ``not-accessible``, and carried a
``DEFVAL`` on each that no clause in the module asks for.

The engine modules are not pysnmp's to define -- the RFCs define them and
pysmi's bundle carries the ASN.1 -- but pysnmp commits a rendering of them so
that starting an engine needs no pysmi. A committed rendering is a copy, and a
copy drifts, which is the whole reason the first set is checked. So the same
check covers both.

The rendering is checked rather than trusted: re-render, and compare. What a
relation the ASN.1 cannot state looks like now is a file in
``pysnmp/smi/mibs/behavior/``, which this does not touch.
"""

import ast
import os
import pathlib

import pytest

import pysnmp
from pysnmp.smi.builder import DirMibSource, MibBuilder
from tools.regenerate_mibs import (
    ASN1_DIR,
    ENGINE_MODULES,
    MODULES,
    OUTPUT_DIR,
    OWN_MODULES,
    _dependency_asn1,
    build,
)

#: Where pysnmp's Python lives, which is what the sweep below reads.
PACKAGE = pathlib.Path(pysnmp.__file__).parent


def _namedModules() -> dict[str, set[str]]:
    """Every MIB module pysnmp names as a literal, and where it names it.

    A module reaches an engine by name: ``importSymbols("SNMPv2-TM", ...)`` or
    ``loadModules("SNMPv2-TM")``. Reading those names out of the source is what
    makes :py:data:`MODULES` checkable rather than asserted -- the list was
    arrived at by making some configuration calls and writing down what got
    loaded, and what that missed was the calls nobody made.

    Names built at run time are not here and cannot be: `MibViewController` and
    `ObjectIdentity` import from whatever module a caller asks for, which is
    the whole point of them. Those are a compiler's or a corpus's to answer.
    What this covers is the names pysnmp itself chose, which are the ones an
    install has to carry however it was installed.

    Returns
    -------
        Module name to the ``path:line`` of each mention.
    """
    named: dict[str, set[str]] = {}

    for path in sorted(PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue

            function = node.func
            if isinstance(function, ast.Attribute):
                name = function.attr
            elif isinstance(function, ast.Name):
                name = function.id
            else:
                continue

            if name not in ("importSymbols", "loadModule", "loadModules"):
                continue

            # loadModules() takes module names all the way along; the others
            # take one module and then the symbols wanted from it.
            arguments = node.args if name != "importSymbols" else node.args[:1]

            for argument in arguments:
                if isinstance(argument, ast.Constant) and isinstance(
                    argument.value, str
                ):
                    named.setdefault(argument.value, set()).add(
                        f"{path.relative_to(PACKAGE.parent)}:{node.lineno}"
                    )

    return named


#: The sweep, run once at collection so it can parametrize.
NAMED_MODULES = _namedModules()


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


@pytest.mark.parametrize("module", OWN_MODULES)
def test_the_asn1_source_is_present(module):
    assert os.path.exists(os.path.join(ASN1_DIR, f"{module}.txt"))


@pytest.mark.parametrize("module", ENGINE_MODULES)
def test_the_engine_module_asn1_comes_from_pysmi(module):
    # pysnmp does not carry ASN.1 for the modules the RFCs define, and should
    # not: a second copy of a standard module's source is a second thing to
    # keep current. What it carries is a rendering, which this file checks
    # against the one copy that exists. pysmi's bundle names those files by
    # module name with no extension, unlike docs/mibs.
    assert os.path.exists(os.path.join(_dependency_asn1(), module))


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


class TestEveryNamedModuleIsShipped:
    """pysnmp can load every module it names, from what it ships alone.

    The property ``MODULES`` exists for, stated as the thing it actually has to
    guarantee. Three modules were missing from that list for as long as it
    existed -- ``SNMPv2-TM`` and ``TRANSPORT-ADDRESS-MIB``, which
    ``addTargetAddr()`` imports, and ``SNMP-NOTIFICATION-MIB``, which
    ``addNotificationTarget()`` imports -- so a pysmi-less install raised
    ``MibNotFoundError`` on every GET and every trap it tried to send. Nothing
    noticed, because the list was maintained by hand and the suites that ran
    without pysmi ran configuration rather than operations.

    Reading the names out of the source is what makes the next one fail here
    rather than in an install. A new ``importSymbols("SOME-MIB", ...)`` in
    pysnmp either names something pysnmp ships or fails the suite.
    """

    @staticmethod
    def _shipped() -> MibBuilder:
        """A builder that can see pysnmp's own modules and nothing else.

        Not the default sources: those include pysmi's generated bundle, which
        would answer for every one of these and measure nothing. This is the
        pysmi-less install, in process.
        """
        builder = MibBuilder()
        builder.setMibSources(
            DirMibSource(OUTPUT_DIR),
            DirMibSource(os.path.join(OUTPUT_DIR, "instances")),
        )

        return builder

    def test_the_sweep_found_the_modules_it_should(self):
        # A sweep that found nothing would parametrize nothing and pass in
        # silence, which is the failure mode of every test that generates its
        # own cases. These are named by pysnmp/entity/config.py and will be for
        # as long as an engine has a configuration.
        assert {
            "SNMP-NOTIFICATION-MIB",
            "SNMP-TARGET-MIB",
            "SNMPv2-TM",
            "TRANSPORT-ADDRESS-MIB",
        } <= set(NAMED_MODULES)

    @pytest.mark.parametrize("module", sorted(NAMED_MODULES))
    def test_a_module_pysnmp_names_loads_from_what_it_ships(self, module):
        try:
            self._shipped().loadModule(module)
        except Exception as exc:  # noqa: BLE001 -- the message is the report
            mentions = ", ".join(sorted(NAMED_MODULES[module]))
            pytest.fail(
                f"pysnmp names {module} at {mentions} but does not ship it, so a "
                f"pysmi-less install raises on whatever reaches that line. Add it "
                f"to ENGINE_MODULES in tools/regenerate_mibs.py and re-render. "
                f"({type(exc).__name__}: {exc})"
            )

    def test_a_module_pysnmp_does_not_ship_really_does_fail(self):
        # The negative control. loadModules() is lenient about a module it
        # cannot find, so a check written on it would pass for everything.
        from pysnmp.smi import error

        with pytest.raises(error.MibNotFoundError):
            self._shipped().loadModule("IF-MIB")
