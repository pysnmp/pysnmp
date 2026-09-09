"""pysnmp runs an SNMP engine with pysmi not installed.

``pysnmp-pysmi`` is an optional dependency -- ``pip install pysnmplib[compile]``
asks for it -- and what makes that honest is that nothing on the engine path
imports it. pysnmp commits a rendering of the seven standard modules an engine
resolves during start-up and configuration, so the modules are there whether or
not pysmi is.

That is easy to say and easy to lose: one new ``importSymbols()`` of a module
pysnmp does not carry turns a working install into an ``MibLoadError`` that no
test in this suite would notice, because CI installs the dev group and the dev
group has pysmi. So the import is blocked and an engine started anyway.

In a subprocess, deliberately. A ``sys.meta_path`` hook cannot un-import what
another test already imported, and ``pysnmp.smi.compiler`` binds its pysmi
names at module import; a fresh interpreter is the only way to see what a
pysmi-less install actually sees.
"""

import subprocess
import sys
import textwrap

import pytest

#: Refuse pysmi to the interpreter, ahead of every real finder.
BLOCK = """
import sys


class NoPysmi:
    def find_spec(self, name, path=None, target=None):
        if name == "pysmi" or name.startswith("pysmi."):
            raise ImportError(f"No module named {name!r}")

        return None


sys.meta_path.insert(0, NoPysmi())
"""


def run(body: str) -> str:
    """Run ``body`` in a fresh interpreter that has no pysmi.

    Args:
        body: source to run after the import block is installed

    Returns:
        Everything the child printed to stdout.

    Raises:
        AssertionError: the child exited non-zero.
    """
    source = BLOCK + textwrap.dedent(body)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"a pysmi-less interpreter could not run this:\n{result.stderr}"
    )

    return result.stdout


def test_pysmi_is_really_blocked():
    # Guard the guard. If the block stopped working, every other test in this
    # file would pass by importing the pysmi that CI installs for the dev
    # group, and would be measuring nothing at all.
    assert (
        run("""
        try:
            import pysmi
        except ImportError as exc:
            print(exc)
        else:
            raise AssertionError("pysmi imported anyway")
        """).strip()
        == "No module named 'pysmi'"
    )


def test_an_engine_starts():
    assert (
        run("""
        from pysnmp.entity.engine import SnmpEngine

        print(SnmpEngine() is not None)
        """).strip()
        == "True"
    )


def test_a_v3_engine_configures():
    # The configuration calls are what reach for SNMP-USER-BASED-SM-MIB,
    # SNMP-VIEW-BASED-ACM-MIB and SNMP-TARGET-MIB. A bare SnmpEngine() does
    # not, so starting one proves less than it looks like it does.
    assert (
        run("""
        from pysnmp.entity import config, engine

        snmpEngine = engine.SnmpEngine()
        config.addV3User(
            snmpEngine,
            "usr",
            config.usmHMACSHAAuthProtocol,
            "authkey1",
            config.usmAesCfb128Protocol,
            "privkey1",
        )
        config.addVacmUser(
            snmpEngine, 3, "usr", "authPriv", (1, 3, 6), (1, 3, 6), (1, 3, 6)
        )
        config.addTargetParams(snmpEngine, "params", "usr", "authPriv")

        print(len(snmpEngine.getMibBuilder().mibSymbols) > 0)
        """).strip()
        == "True"
    )


def test_names_resolve():
    assert (
        run("""
        from pysnmp.entity.engine import SnmpEngine
        from pysnmp.smi.rfc1902 import ObjectIdentity
        from pysnmp.smi.view import MibViewController

        mibViewController = MibViewController(SnmpEngine().getMibBuilder())
        objectIdentity = ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)
        objectIdentity.resolveWithMib(mibViewController)

        print(objectIdentity.prettyPrint())
        """).strip()
        == "SNMPv2-MIB::sysDescr.0"
    )


def test_the_compiler_refuses_by_name():
    # The one thing that genuinely needs pysmi. It refused this way before
    # pysmi was optional too -- anyone who had not installed it saw exactly
    # this -- so what changed is who sees it, not what they see.
    assert "MIB compiler not available" in run("""
        from pysnmp.entity.engine import SnmpEngine
        from pysnmp.smi import compiler, error

        try:
            compiler.addMibCompiler(SnmpEngine().getMibBuilder())
        except error.SmiError as exc:
            print(exc)
        else:
            raise AssertionError("the compiler did not refuse")
        """)


def test_the_compiler_stays_quiet_when_asked_to():
    # ifAvailable is how a caller says "add one if you can". It has to stay
    # silent rather than raise, or every optional-compiler code path breaks
    # the moment pysmi is not installed.
    assert (
        run("""
        from pysnmp.entity.engine import SnmpEngine
        from pysnmp.smi import compiler

        compiler.addMibCompiler(SnmpEngine().getMibBuilder(), ifAvailable=True)
        print("quiet")
        """).strip()
        == "quiet"
    )


#: The modules a pysmi-less install has to be able to load.
#:
#: Spelled out rather than imported from ``tools.regenerate_mibs``, which
#: imports pysmi -- so importing it here would make this file's collection
#: depend on the thing the file exists to do without.
#: ``test_this_list_matches_what_is_rendered`` keeps the two in step.
ENGINE_MODULES = (
    "SNMP-COMMUNITY-MIB",
    "SNMP-FRAMEWORK-MIB",
    "SNMP-MPD-MIB",
    "SNMP-TARGET-MIB",
    "SNMP-USER-BASED-SM-MIB",
    "SNMP-VIEW-BASED-ACM-MIB",
    "SNMPv2-MIB",
)


@pytest.mark.parametrize("module", ENGINE_MODULES)
def test_the_engine_modules_load(module):
    assert (
        run(f"""
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("{module}")
        print("{module}" in mibBuilder.mibSymbols)
        """).strip()
        == "True"
    )


def test_this_list_matches_what_is_rendered():
    from tools.regenerate_mibs import ENGINE_MODULES as RENDERED

    assert set(ENGINE_MODULES) == set(RENDERED)
