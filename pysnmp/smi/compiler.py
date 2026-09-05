#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
import sys
from pathlib import Path

defaultSources = ["file:///usr/share/snmp/mibs", "file:///usr/share/mibs"]

if sys.platform[:3] == "win":
    defaultDest = str(Path.home() / "PySNMP Configuration" / "mibs")
else:
    defaultDest = str(Path.home() / ".pysnmp" / "mibs")

defaultBorrowers = []

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
        def addMibCompiler(mibBuilder, **kwargs):
            if not kwargs.get("ifAvailable"):
                raise error.SmiError("MIB compiler not available: %s" % errorMsg)

        return addMibCompiler

    addMibCompiler = addMibCompilerDecorator(e)

else:

    def addMibCompiler(mibBuilder, **kwargs):
        if kwargs.get("ifNotAdded") and mibBuilder.getMibCompiler():
            return

        compiler = MibCompiler(
            parserFactory(**smiV1Relaxed)(),
            PySnmpCodeGen(),
            PyFileWriter(kwargs.get("destination") or defaultDest),
        )

        compiler.add_sources(*getReadersFromUrls(*kwargs.get("sources") or defaultSources))

        compiler.add_searchers(StubSearcher(*baseMibs))
        compiler.add_searchers(
            *[PyPackageSearcher(x.fullPath()) for x in mibBuilder.getMibSources()]
        )
        compiler.add_borrowers(
            *[
                PyFileBorrower(x, genTexts=mibBuilder.loadTexts)
                for x in getReadersFromUrls(
                    *kwargs.get("borrowers") or defaultBorrowers, **dict(lowcaseMatching=False)
                )
            ]
        )

        mibBuilder.setMibCompiler(compiler, kwargs.get("destination") or defaultDest)
