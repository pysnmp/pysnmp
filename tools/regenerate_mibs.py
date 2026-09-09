#!/usr/bin/env python
"""Render the MIB modules pysnmp ships from the ASN.1 they are defined by.

Two sets, for two different reasons.

**pysnmp's own** -- ``PYSNMP-MIB``, ``PYSNMP-SOURCE-MIB`` and
``PYSNMP-USM-MIB``. pysnmp publishes these, and the ASN.1 that defines them is
in ``docs/mibs``.

**The engine layer** -- the seven standard modules an ``SnmpEngine`` cannot
start without. These are not pysnmp's to define; RFC 3411-3418 and RFC 3584
define them, and the ASN.1 comes from pysmi's bundle. pysnmp carries a
rendering of them so that starting an engine needs no pysmi at run time, which
is what makes ``pysnmp-pysmi`` an optional dependency rather than a required
one. #196 draws that boundary: engine configuration and live state are out of
the corpus's scope because a manager-only deployment needs them too, and that
floor does not grow with the number of MIBs anyone translates.

Rendering them here rather than depending on pysmi's copy keeps pysmi the sole
producer of the artifact shape -- it is still pysmi's code generator and
pysmi's ASN.1 that produce these -- and moves it from install time to build
time.

Until 2026 pysnmp's own three were pysmi-0.1.3 output from April 2017, edited
by hand and never regenerated, and they had drifted from their own ASN.1 --
see pysnmp/pysmi#231 for the same story in five standard modules. Nothing here
is hand-edited: run this, commit what it writes. A relation the ASN.1 cannot
state goes in ``pysnmp/smi/mibs/behavior/``, not into the rendered output.

``tests/test_generated_mibs.py`` renders the same modules and compares them to
what is committed, so drift fails the suite rather than accumulating.

Usage::

    python tools/regenerate_mibs.py            # write the modules
    python tools/regenerate_mibs.py --check    # report drift, write nothing
"""

import argparse
import os
import subprocess
import sys

import pysmi
from pysmi.codegen import PySnmpCodeGen
from pysmi.compiler import MibCompiler
from pysmi.parser import SmiV2Parser
from pysmi.reader import FileReader
from pysmi.searcher import StubSearcher
from pysmi.writer import CallbackWriter

#: The MIBs pysnmp defines, from the ASN.1 in ``docs/mibs``.
OWN_MODULES = ("PYSNMP-MIB", "PYSNMP-SOURCE-MIB", "PYSNMP-USM-MIB")

#: The standard modules an ``SnmpEngine`` resolves during start-up and
#: configuration, from pysmi's bundled ASN.1.
#:
#: Measured, not guessed: build an engine, add a v3 user, a VACM entry and a
#: target params entry, then ask the builder which modules it loaded. These
#: seven are what it reaches for, and their import closure adds nothing --
#: everything they import is already in ``pysnmp/smi/mibs``.
#: ``tests/test_engine_mibs.py`` re-measures it, so a new import fails the
#: suite rather than surfacing as an ImportError in a pysmi-less install.
ENGINE_MODULES = (
    "SNMP-COMMUNITY-MIB",
    "SNMP-FRAMEWORK-MIB",
    "SNMP-MPD-MIB",
    "SNMP-TARGET-MIB",
    "SNMP-USER-BASED-SM-MIB",
    "SNMP-VIEW-BASED-ACM-MIB",
    "SNMPv2-MIB",
)

#: Everything this renders.
MODULES = OWN_MODULES + ENGINE_MODULES

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Where the ASN.1 that defines them lives.
ASN1_DIR = os.path.join(_ROOT, "docs", "mibs")

#: Where the rendered modules go.
OUTPUT_DIR = os.path.join(_ROOT, "pysnmp", "smi", "mibs")


def _dependency_asn1() -> str:
    """Pysmi's bundled ASN.1, for the standard modules these import from."""
    return os.path.join(os.path.dirname(pysmi.__file__), "mibs", "asn1")


def render(*modules: str) -> dict[str, str]:
    """Render ``modules`` from their ASN.1.

    Args:
        modules: module names; defaults to :py:data:`MODULES`

    Returns
    -------
        Module name to rendered Python.

    Raises
    ------
        RuntimeError: a module did not compile.
    """
    wanted = modules or MODULES
    rendered: dict[str, str] = {}

    compiler = MibCompiler(
        SmiV2Parser(),
        PySnmpCodeGen(),
        CallbackWriter(lambda name, text, ctx: rendered.__setitem__(name, text)),
    )
    compiler.add_sources(FileReader(ASN1_DIR), FileReader(_dependency_asn1()))

    # PYSNMP-USM-MIB is one of pysmi's baseMibs -- the modules it treats as
    # supplied by the runtime and so declines to compile. That list naming a
    # MIB pysnmp alone publishes is the same layering leak the behavior
    # fragments were: dropped here so the module pysnmp defines is rendered
    # from the ASN.1 pysnmp defines it in.
    stubs = [name for name in PySnmpCodeGen.baseMibs if name not in wanted]
    compiler.add_searchers(StubSearcher(*stubs))

    status = compiler.compile(*wanted, noDeps=False, rebuild=True, genTexts=True)

    failed = [name for name in wanted if status.get(name) not in ("compiled",)]
    if failed:
        raise RuntimeError(f"did not compile: {', '.join(failed)} (status {status})")

    return {name: rendered[name] for name in wanted}


def format_source(text: str, path: str) -> str:
    """Run the repository's formatter over rendered output.

    The rendered modules are committed and read by people, and every other
    module in the tree is formatted. Done here rather than by hand so that
    what this writes is what ``--check`` compares against.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ruff", "format", "--stdin-filename", path, "-"],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ruff format failed for {path}: {result.stderr}")

    return result.stdout


def build(*modules: str) -> dict[str, str]:
    """Render and format ``modules``, keyed by the path each belongs at."""
    built = {}

    for name, text in render(*modules).items():
        path = os.path.join(OUTPUT_DIR, f"{name}.py")
        built[path] = format_source(text, path)

    return built


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report modules that differ from their ASN.1 and write nothing",
    )
    parser.add_argument(
        "modules", nargs="*", help=f"modules to render (default: {' '.join(MODULES)})"
    )
    args = parser.parse_args()

    built = build(*args.modules)
    drifted = []

    for path, text in sorted(built.items()):
        name = os.path.basename(path)

        if os.path.exists(path):
            with open(path, encoding="utf-8") as fileObj:
                if fileObj.read() == text:
                    print(f"unchanged  {name}")
                    continue

        drifted.append(name)

        if args.check:
            print(f"DRIFTED    {name}")
            continue

        with open(path, "w", encoding="utf-8") as fileObj:
            fileObj.write(text)

        print(f"written    {name}")

    if args.check and drifted:
        print(
            f"\n{len(drifted)} module(s) differ from their ASN.1. "
            f"Run: python tools/regenerate_mibs.py",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
