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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: Where `addMibCompiler` compiles from when nothing else says.
#:
#: Local only, and deliberately: attaching a compiler should not put an SNMP
#: application on the network for MIB content it did not ask for. To compile
#: from the published corpus, name it: pass
#: ``https://data.mibsdepot.com/asn1/@mib@`` in ``sources=``, or set the same URL
#: in `PYSNMP_MIB_SOURCES`. Naming it is also what puts it in the order the
#: caller wants relative to any local tree.
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


#: The environment variable the XDG Base Directory specification defines as
#: the root of a user's cache.
#:
#: Only consulted where the spec applies. An entry that is not absolute is
#: ignored, which the spec requires.
CACHE_HOME_ENV = "XDG_CACHE_HOME"

#: Where Windows puts per-machine user data, cache included.
LOCAL_APP_DATA_ENV = "LOCALAPPDATA"


def _legacyCacheDirectory(home: Path, platform: str) -> Path:
    """Where releases before this one compiled to."""
    if platform[:3] == "win":
        return home / "PySNMP Configuration" / "mibs"

    return home / ".pysnmp" / "mibs"


def cacheDirectory(
    home: "str | Path | None" = None,
    platform: "str | None" = None,
    environ: "Mapping[str, str] | None" = None,
) -> str:
    """Where compiled MIBs are written, and read back from, by default.

    Compiled MIBs are regenerable, user-specific and non-essential, which is
    what every platform's cache convention is for. The old ``~/.pysnmp/mibs``
    was none of those things to a backup tool, which swept a regenerable cache
    into the user's home-directory archive.

    Args:
        home: the user's home directory, read from the environment when not
            given.
        platform: the `sys.platform` string, read from the running
            interpreter when not given.
        environ: the environment, read from `os.environ` when not given.
            These three are injected by the tests, which have no business
            editing the real ones for something this small.

    Returns
    -------
        The directory, as a string, in the form the compiler wants.

    Notes
    -----
        A populated legacy directory wins, so that upgrading does not orphan a
        cache someone already has and silently recompile everything in it. The
        new location is used only where there is nothing to keep.

        Otherwise the platform's own convention applies: ``$XDG_CACHE_HOME``
        and then ``~/.cache`` on Linux and the BSDs, ``~/Library/Caches`` on
        macOS, ``%LOCALAPPDATA%`` on Windows. An explicitly set
        ``XDG_CACHE_HOME`` is honoured on macOS too -- it is not that
        platform's convention, but someone who set it meant it.

        This is the default and nothing more: ``destination=`` passed to
        `addMibCompiler` still wins, as it always did.

        The rules are short enough to write out, so they are written out rather
        than taken as a dependency. `platformdirs` implements the same three
        conventions and more, and is the right answer for a package that can
        afford another install-time requirement; pysnmp has two and would
        rather keep it that way.
    """
    homePath = Path.home() if home is None else Path(home)
    platformName = sys.platform if platform is None else platform
    variables: Mapping[str, str] = os.environ if environ is None else environ

    legacy = _legacyCacheDirectory(homePath, platformName)
    if legacy.is_dir():
        return str(legacy)

    if platformName[:3] == "win":
        localAppData = variables.get(LOCAL_APP_DATA_ENV)
        base = (
            Path(localAppData)
            if localAppData and os.path.isabs(localAppData)
            else homePath / "AppData" / "Local"
        )
        # LOCALAPPDATA holds configuration as well as cache, so the
        # convention there is a "Cache" segment to tell them apart.
        return str(base / "pysnmp" / "Cache" / "mibs")

    cacheHome = variables.get(CACHE_HOME_ENV)
    if cacheHome and os.path.isabs(cacheHome):
        base = Path(cacheHome)
    elif platformName == "darwin":
        base = homePath / "Library" / "Caches"
    else:
        base = homePath / ".cache"

    return str(base / "pysnmp" / "mibs")


#: Where `addMibCompiler` writes compiled MIBs when no ``destination=`` says
#: otherwise. Settled once, at import, so that it does not change under a
#: running application.
defaultDest = cacheDirectory()

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
