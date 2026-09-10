#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Compiling ASN.1 to loadable modules at run time, when pysmi is installed.

pysmi is an optional dependency: install `pysnmplib[compile]` to get it.
Without it `addMibCompiler` raises `SmiError` naming the missing import.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any

defaultSources = ["file:///usr/share/snmp/mibs", "file:///usr/share/mibs"]

#: Where to look for ASN.1 to compile, as `os.pathsep`-separated entries.
#:
#: The compile-side counterpart of `PYSNMP_MIB_DIRS` and `PYSNMP_MIB_DBS`,
#: which name generated `.py` and corpora respectively. Only meaningful with
#: the `[compile]` extra installed, since without pysmi nothing compiles.
#:
#: Set, it replaces `defaultSources` rather than adding to it -- the same rule
#: `PYSNMP_MIB_DIRS` follows, and the one that lets a container image say where
#: its MIBs are without inheriting two paths from the host distribution that do
#: not exist in it. An explicit ``sources=`` still wins: a caller who passed a
#: value meant it.
SOURCES_ENV = "PYSNMP_MIB_SOURCES"

#: A URL scheme at the start of an entry, so that splitting does not cut
#: ``https://example.org/mibs`` in half on POSIX, where `os.pathsep` is the
#: colon that follows the scheme. A scheme is never a single character -- that
#: is a Windows drive letter, which pysmi's reader factory already recognises
#: as a local path.
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]+$")


def sourcesFromEnvironment(value: "str | None" = None) -> "list[str] | None":
    """The ASN.1 sources named by `PYSNMP_MIB_SOURCES`, or ``None`` if unset.

    Args:
        value: the raw variable, read from the environment when not given.
            Passed in by the tests, which have no business editing `os.environ`
            for something this small.

    Returns
    -------
        The entries in the order they were written, or ``None`` where the
        variable is unset or holds nothing but separators -- which is not the
        same as an empty list, and has to stay distinguishable from it, since
        an empty list would mean "compile from nowhere".
    """
    if value is None:
        value = os.environ.get(SOURCES_ENV)

    if value is None:
        return None

    parts = value.split(os.pathsep)
    sources: list[str] = []

    for part in parts:
        # A bare scheme followed by an entry starting "//" is one URL that the
        # split cut at its colon; put it back together.
        if (
            sources
            and part.startswith("//")
            and _SCHEME.match(sources[-1])
            and os.pathsep == ":"
        ):
            sources[-1] = f"{sources[-1]}:{part}"
            continue

        if part:
            sources.append(part)

    return sources or None


if sys.platform[:3] == "win":
    defaultDest = str(Path.home() / "PySNMP Configuration" / "mibs")
else:
    defaultDest = str(Path.home() / ".pysnmp" / "mibs")

defaultBorrowers: list[Any] = []

try:
    from pysmi.borrower.pyfile import PyFileBorrower
    from pysmi.codegen.pysnmp import PySnmpCodeGen, baseMibs
    from pysmi.compiler import MibCompiler
    from pysmi.parser.dialect import smiV1Relaxed
    from pysmi.parser.smi import parserFactory
    from pysmi.reader.url import getReadersFromUrls
    from pysmi.searcher.pypackage import PyPackageSearcher
    from pysmi.searcher.stub import StubSearcher
    from pysmi.writer.pyfile import PyFileWriter

except ImportError as e:
    from pysnmp.smi import error

    def addMibCompilerDecorator(errorMsg):
        """Build the stand-in `addMibCompiler()` used when pysmi is not installed.

        The import error is captured here so the failure names what was missing,
        rather than reporting only that no compiler is configured.
        """

        def addMibCompiler(mibBuilder, **kwargs):
            if not kwargs.get("ifAvailable"):
                raise error.SmiError(f"MIB compiler not available: {errorMsg}")

        return addMibCompiler

    addMibCompiler = addMibCompilerDecorator(e)

else:

    def addMibCompiler(mibBuilder, **kwargs):
        """Attach a MIB compiler to the builder, so ASN.1 can be compiled on demand.

        Without pysmi installed this raises `SmiError` naming the missing import,
        unless `ifAvailable` is set. `ifNotAdded` makes the call a no-op where a
        compiler is already attached.

        Where to compile from is settled in three steps: an explicit
        ``sources=``, then `PYSNMP_MIB_SOURCES`, then `defaultSources`.
        """
        if kwargs.get("ifNotAdded") and mibBuilder.getMibCompiler():
            return

        compiler = MibCompiler(
            parserFactory(**smiV1Relaxed)(),
            PySnmpCodeGen(),
            PyFileWriter(kwargs.get("destination") or defaultDest),
        )

        compiler.add_sources(
            *getReadersFromUrls(
                *kwargs.get("sources") or sourcesFromEnvironment() or defaultSources
            )
        )

        compiler.add_searchers(StubSearcher(*baseMibs))
        compiler.add_searchers(
            *[PyPackageSearcher(x.fullPath()) for x in mibBuilder.getMibSources()]
        )
        compiler.add_borrowers(
            *[
                PyFileBorrower(x, genTexts=mibBuilder.loadTexts)
                for x in getReadersFromUrls(
                    *kwargs.get("borrowers") or defaultBorrowers,
                    lowcaseMatching=False,
                )
            ]
        )

        mibBuilder.setMibCompiler(compiler, kwargs.get("destination") or defaultDest)
