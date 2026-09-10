#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Compiling ASN.1 to loadable modules at run time, when pysmi is installed.

pysmi is an optional dependency: install `pysnmplib[compile]` to get it.
Without it `addMibCompiler` raises `SmiError` naming the missing import.
"""

import sys
from pathlib import Path
from typing import Any

defaultSources = ["file:///usr/share/snmp/mibs", "file:///usr/share/mibs"]

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
        """
        if kwargs.get("ifNotAdded") and mibBuilder.getMibCompiler():
            return

        compiler = MibCompiler(
            parserFactory(**smiV1Relaxed)(),
            PySnmpCodeGen(),
            PyFileWriter(kwargs.get("destination") or defaultDest),
        )

        compiler.add_sources(
            *getReadersFromUrls(*kwargs.get("sources") or defaultSources)
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
