#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
import os
import sys

defaultSources = ["file:///usr/share/snmp/mibs", "file:///usr/share/mibs"]

if sys.platform[:3] == "win":
    defaultDest = os.path.join(os.path.expanduser("~"), "PySNMP Configuration", "mibs")
else:
    defaultDest = os.path.join(os.path.expanduser("~"), ".pysnmp", "mibs")

defaultBorrowers = []

try:
    from pysmi.borrower.pyfile import PyFileBorrower
    from pysmi.codegen.pysnmp import PySnmpCodeGen, baseMibs
    from pysmi.compiler import MibCompiler

    try:
        from pysmi.parser.dialect import smi_v1_relaxed
    except ImportError:  # pysmi < 2.0
        from pysmi.parser.dialect import smiV1Relaxed as smi_v1_relaxed
    try:
        from pysmi.parser.smi import parser_factory
    except ImportError:  # pysmi < 2.0
        from pysmi.parser.smi import parserFactory as parser_factory
    try:
        from pysmi.reader.url import get_readers_from_urls
    except ImportError:  # pysmi < 2.0
        from pysmi.reader.url import getReadersFromUrls as get_readers_from_urls
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
            parser_factory(**smi_v1_relaxed)(),
            PySnmpCodeGen(),
            PyFileWriter(kwargs.get("destination") or defaultDest),
        )

        add_sources = getattr(compiler, "add_sources", None) or compiler.addSources
        add_searchers = getattr(compiler, "add_searchers", None) or compiler.addSearchers
        add_borrowers = getattr(compiler, "add_borrowers", None) or compiler.addBorrowers

        add_sources(*get_readers_from_urls(*kwargs.get("sources") or defaultSources))

        add_searchers(StubSearcher(*baseMibs))
        add_searchers(*[PyPackageSearcher(x.fullPath()) for x in mibBuilder.getMibSources()])
        add_borrowers(
            *[
                PyFileBorrower(x, genTexts=mibBuilder.loadTexts)
                for x in get_readers_from_urls(
                    *kwargs.get("borrowers") or defaultBorrowers, **dict(lowcaseMatching=False)
                )
            ]
        )

        mibBuilder.setMibCompiler(compiler, kwargs.get("destination") or defaultDest)
