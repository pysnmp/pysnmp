#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

import dis
import importlib
import importlib.machinery
import importlib.util
import marshal
import os
import struct
import time
import traceback
from errno import ENOENT
from typing import Any, cast

from pysnmp import debug
from pysnmp import version as pysnmp_version
from pysnmp.smi import error

PY_MAGIC_NUMBER = importlib.util.MAGIC_NUMBER
SOURCE_SUFFIXES = importlib.machinery.SOURCE_SUFFIXES
BYTECODE_SUFFIXES = importlib.machinery.BYTECODE_SUFFIXES

PY_SUFFIXES = SOURCE_SUFFIXES + BYTECODE_SUFFIXES

classTypes = (type,)


class __AbstractMibSource:
    def __init__(self, srcName: str) -> None:
        self._srcName = srcName
        self.__inited = None
        debug.logger & debug.flagBld and debug.logger(f"trying {self}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._srcName!r})"

    def _uniqNames(self, names: list[str]) -> tuple[str, ...]:
        u: set[str] = set()

        for f in names:
            if f.startswith("__init__."):
                continue

            u.update(f[: -len(sfx)] for sfx in PY_SUFFIXES if f.endswith(sfx))

        return tuple(u)

    # MibSource API follows

    def fullPath(self, *args: Any) -> str:
        f = args[0] if args else ""
        sfx = args[1] if len(args) > 1 else ""
        return self._srcName + (f and (os.sep + f + sfx) or "")

    def init(self) -> Any:
        if self.__inited is None:
            self.__inited = self._init()
            if self.__inited is self:
                self.__inited = True
        if isinstance(self.__inited, bool) and self.__inited:
            return self

        else:
            return self.__inited

    def listdir(self) -> tuple[str, ...]:
        return self._listdir()

    def read(self, f: str) -> Any:
        pycTime: float = -1
        pyTime: float = -1

        for pycSfx in BYTECODE_SUFFIXES:
            try:
                pycData, pycPath = self._getData(f + pycSfx, "rb")

            except OSError as why:
                if why.errno == ENOENT:
                    debug.logger & debug.flagBld and debug.logger(
                        f"file {f + pycSfx} access error: {why}"
                    )

                else:
                    raise error.MibLoadError(
                        f"MIB file {f + pycSfx} access error: {why}"
                    ) from why

            else:
                if pycData[:4] == PY_MAGIC_NUMBER:
                    # PEP 552 (Python 3.7+) uses a 16-byte header:
                    #   magic (4) + bitfield (4) + word3 (4) + word4 (4)
                    # When bitfield & 1 == 0, word3 is the timestamp and
                    # word4 is the source size (timestamp-based invalidation).
                    # When bitfield & 1 == 1, word3+word4 form a hash
                    # (hash-based invalidation, no timestamp).
                    bitfield = struct.unpack("<L", pycData[4:8])[0]
                    if not (bitfield & 1):
                        # Timestamp-based: extract timestamp for staleness check
                        pycTime = struct.unpack("<L", pycData[8:12])[0]
                    # Strip the full 16-byte header to get marshalled code
                    pycData = pycData[16:]
                    debug.logger & debug.flagBld and debug.logger(
                        f"file {pycPath} mtime {pycTime}"
                    )
                    break

                else:
                    debug.logger & debug.flagBld and debug.logger(
                        f"bad magic in {pycPath}"
                    )

        for pySfx in SOURCE_SUFFIXES:
            try:
                pyTime = self._getTimestamp(f + pySfx)

            except OSError as why:
                if why.errno == ENOENT:
                    debug.logger & debug.flagBld and debug.logger(
                        f"file {f + pySfx} access error: {why}"
                    )

                else:
                    raise error.MibLoadError(
                        f"MIB file {f + pySfx} access error: {why}"
                    ) from why

            else:
                debug.logger & debug.flagBld and debug.logger(
                    f"file {f + pySfx} mtime {pyTime}"
                )
                break

        if pycTime != -1 and pycTime >= pyTime:
            # The .pyc is one this package compiled from a MIB it found on its
            # own MIB path, not untrusted input.
            return marshal.loads(pycData), pycSfx  # noqa: S302

        if pyTime != -1:
            modData, pyPath = self._getData(f + pySfx, "r")
            return compile(modData, pyPath, "exec"), pyPath

        raise OSError(ENOENT, "No suitable module found", f)

    # Interfaces for subclasses
    def _init(self) -> Any:
        raise NotImplementedError

    def _listdir(self) -> tuple[str, ...]:
        raise NotImplementedError

    def _getTimestamp(self, f: str) -> float:
        raise NotImplementedError

    def _getData(self, f: str, mode: str) -> tuple[Any, str]:
        raise NotImplementedError


class ZipMibSource(__AbstractMibSource):
    # zipimport.zipimporter carries the archive directory as the private
    # `_files`, which is what this class reads; typeshed describes neither it
    # nor the loader `__import__` hands back, so there is nothing narrower to
    # say here than what the hasattr() guard below already checks.
    __loader: Any

    def _init(self) -> Any:
        try:
            p = __import__(self._srcName, globals(), locals(), ["__init__"])
            if hasattr(p, "__loader__") and hasattr(p.__loader__, "_files"):
                self.__loader = p.__loader__
                self._srcName = self._srcName.replace(".", os.sep)
                return self
            elif getattr(p, "__file__", None):
                # Dir relative to PYTHONPATH. __file__ is Optional -- a
                # namespace package has none -- but the guard above has
                # already established this one has a path.
                return DirMibSource(os.path.split(cast(str, p.__file__))[0]).init()
            else:
                raise error.MibLoadError(f"{p} access error")

        except ImportError:
            # Dir relative to CWD
            return DirMibSource(self._srcName).init()

    @staticmethod
    def _parseDosTime(dosdate: int, dostime: int) -> float:
        t = (
            ((dosdate >> 9) & 0x7F) + 1980,  # year
            ((dosdate >> 5) & 0x0F),  # month
            dosdate & 0x1F,  # mday
            (dostime >> 11) & 0x1F,  # hour
            (dostime >> 5) & 0x3F,  # min
            (dostime & 0x1F) * 2,  # sec
            -1,  # wday
            -1,  # yday
            -1,
        )  # dst
        return time.mktime(t)

    def _listdir(self) -> tuple[str, ...]:
        names = []
        # noinspection PyProtectedMember
        for f in self.__loader._files:
            d, f = os.path.split(f)
            if d == self._srcName:
                names.append(f)
        return tuple(self._uniqNames(names))

    def _getTimestamp(self, f: str) -> float:
        p = os.path.join(self._srcName, f)
        # noinspection PyProtectedMember
        if p in self.__loader._files:
            # noinspection PyProtectedMember
            return self._parseDosTime(
                self.__loader._files[p][6], self.__loader._files[p][5]
            )
        else:
            raise OSError(ENOENT, "No such file in ZIP archive", p)

    def _getData(self, f: str, mode: str | None = None) -> tuple[Any, str]:
        p = os.path.join(self._srcName, f)
        try:
            return self.__loader.get_data(p), p

        except Exception as why:  # ZIP code seems to return all kinds of errors
            raise OSError(
                ENOENT, f"File or ZIP archive {p} access error: {why}"
            ) from why


#: The MIB source interface, under a name that survives being written inside a
#: class body: a leading double underscore is mangled with the enclosing class
#: name there, so `__AbstractMibSource` cannot be used in an annotation on
#: MibBuilder.
MibSource = __AbstractMibSource


class DirMibSource(__AbstractMibSource):
    def _init(self) -> Any:
        self._srcName = os.path.normpath(self._srcName)
        return self

    def _listdir(self) -> tuple[str, ...]:
        try:
            return self._uniqNames(os.listdir(self._srcName))
        except OSError as why:
            debug.logger & debug.flagBld and debug.logger(
                f"listdir() failed for {self._srcName}: {why}"
            )
            return ()

    def _getTimestamp(self, f: str) -> float:
        p = os.path.join(self._srcName, f)
        try:
            return os.stat(p)[8]
        except OSError as e:
            raise OSError(ENOENT, f"No such file: {e}", p) from e

    def _getData(self, f: str, mode: str) -> tuple[Any, str]:
        p = os.path.join(self._srcName, "*")
        try:
            if f in os.listdir(self._srcName):  # make FS case-sensitive
                p = os.path.join(self._srcName, f)
                with open(p, mode) as fp:
                    return fp.read(), p

        except OSError as why:
            msg = f"File or directory {p} access error: {why}"

        else:
            msg = f"No such file or directory: {p}"

        raise OSError(ENOENT, msg)


#: The constant pysmi writes into every generated module that has a
#: MODULE-IDENTITY, holding its LAST-UPDATED as ``YYYYMMDDHHMMZ``. See
#: pysnmp/pysmi#205.
MODULE_REVISION = "PYSNMP_MODULE_REVISION"


def revisionOf(codeObj: Any) -> str | None:
    """A generated module's MODULE-IDENTITY revision, without running it.

    Read from the compiled module rather than from its text: the code object
    is what :py:meth:`__AbstractMibSource.read` already hands back, so this
    costs no second read and works for a module distributed as bytecode with
    no ``.py`` beside it.

    Executing the module is not an option. A pysnmp MIB registers its symbols
    into the builder as it runs, so running every candidate to find out which
    one to keep would load all of them. Pattern-matching the source is not one
    either -- ``dis`` reports what the module actually assigns, where a regex
    reports what its text looks like.

    Returns:
        The timestamp, or ``None`` for a module that states no revision --
        every SMIv1 module, and the SMI modules themselves.
    """
    constant = None

    for instruction in dis.get_instructions(codeObj):
        if instruction.opname == "LOAD_CONST":
            constant = instruction.argval

        elif (
            instruction.opname in ("STORE_NAME", "STORE_GLOBAL")
            and instruction.argval == MODULE_REVISION
        ):
            return constant if isinstance(constant, str) else None

    return None


class MibBuilder:
    defaultCoreMibs = os.pathsep.join(("pysnmp.smi.mibs.instances", "pysnmp.smi.mibs"))
    defaultMiscMibs = "pysnmp_mibs"

    #: The modules pysmi generates into every wheel pysnmp already depends on.
    #:
    #: Searched last, which under :py:meth:`MibBuilder._candidates` decides
    #: nothing on its own: a module here still wins wherever it states a newer
    #: MODULE-IDENTITY revision than the copy that was searched first. Position
    #: settles only what the revisions cannot -- a module that states none, or
    #: two copies stating the same one -- where the more specific source, the
    #: one a caller went out of their way to register, is the better guess at
    #: what they meant.
    defaultGeneratedMibs = "pysmi.mibs.pysnmp"

    moduleID = "PYSNMP_MODULE_ID"

    loadTexts = False

    # MIB modules can use this to select the features they can use
    version = pysnmp_version

    #: What a generated MIB module may assume when this builder loads it: which
    #: SMI classes exist, which setters each provides, and what they accept.
    #:
    #: A code generator targets a declared contract version instead of guessing
    #: from ``version``. That guessing is what produced the
    #: ``getattr(mibBuilder, 'version', (0, 0, 0)) > (4, 4, 0)`` branches in
    #: generated output, and a stale belief that three conformance classes lack
    #: ``setReference()`` -- which silently drops MIB text (pysnmp/pysmi#194).
    #:
    #: Bumped only when the contract changes, which is far less often than
    #: ``version``. ``docs/source/docs/loader-contract.rst`` states what each
    #: version covers, and ``tests/test_loader_contract.py`` enforces it.
    loaderContract = (1, 0)

    def __init__(self) -> None:
        self.lastBuildId = self._autoName = 0
        sources = []
        for ev in "PYSNMP_MIB_PKGS", "PYSNMP_MIB_DIRS", "PYSNMP_MIB_DIR":
            if ev in os.environ:
                for m in os.environ[ev].split(os.pathsep):
                    sources.append(ZipMibSource(m))
        if not sources and self.defaultMiscMibs:
            for m in self.defaultMiscMibs.split(os.pathsep):
                sources.append(ZipMibSource(m))
        for m in self.defaultCoreMibs.split(os.pathsep):
            sources.insert(0, ZipMibSource(m))
        if self.defaultGeneratedMibs:
            for m in self.defaultGeneratedMibs.split(os.pathsep):
                sources.append(ZipMibSource(m))
        self.mibSymbols: dict[str, dict[str, Any]] = {}
        self.__mibSources: list[MibSource] = []
        self.__modSeen: dict[str, str] = {}
        self.__modPathsSeen: set[str] = set()
        self.__mibCompiler: Any = None
        self.setMibSources(*sources)

    # MIB compiler management

    def getMibCompiler(self) -> Any:
        return self.__mibCompiler

    def setMibCompiler(self, mibCompiler: Any, destDir: str) -> Any:
        self.addMibSources(DirMibSource(destDir))
        self.__mibCompiler = mibCompiler
        return self

    # MIB modules management

    def addMibSources(self, *mibSources: Any) -> None:
        self.__mibSources.extend([s.init() for s in mibSources])
        debug.logger & debug.flagBld and debug.logger(
            f"addMibSources: new MIB sources {self.__mibSources}"
        )

    def setMibSources(self, *mibSources: Any) -> None:
        self.__mibSources = [s.init() for s in mibSources]
        debug.logger & debug.flagBld and debug.logger(
            f"setMibSources: new MIB sources {self.__mibSources}"
        )

    def getMibSources(self) -> tuple[Any, ...]:
        return tuple(self.__mibSources)

    # Legacy/compatibility methods (won't work for .eggs)
    def setMibPath(self, *mibPaths: str) -> None:
        self.setMibSources(*[DirMibSource(x) for x in mibPaths])

    def getMibPath(self) -> tuple[str, ...]:
        paths: tuple[str, ...] = ()
        for mibSource in self.getMibSources():
            if isinstance(mibSource, DirMibSource):
                paths += (mibSource.fullPath(),)
            else:
                raise error.MibLoadError(
                    f"MIB source is not a plain directory: {mibSource}"
                )
        return paths

    def _candidates(self, modName: str) -> list[tuple[Any, Any, str]]:
        """Every source that can supply *modName*, best match first.

        Source order does not decide. Two sources offering a module are
        offering the same specification at two revisions, and the newer one is
        the answer wherever it is found -- so the newest MODULE-IDENTITY
        revision wins and source order only breaks the tie. A caller who
        registers an older copy of a module does not thereby change behaviour,
        which is the whole point: precedence by position would make that a
        silent downgrade.

        Source order settles it when the revisions cannot: when any candidate
        states none -- every SMIv1 module, and the SMI modules themselves --
        or when they all state the same one. An undated copy cannot be placed
        against a dated one, so a single undated candidate leaves the whole
        decision to order.

        Unlike :py:meth:`pysmi.compiler.MibCompiler._candidate_sources`, this
        is not restricted to a set of names pysmi claims authority over: any
        module found in more than one source is decided this way.
        """
        candidates: list[tuple[Any, Any, str]] = []

        for mibSource in self.__mibSources:
            debug.logger & debug.flagBld and debug.logger(
                f"loadModule: trying {modName} at {mibSource}"
            )
            try:
                codeObj, sfx = mibSource.read(modName)

            except OSError as e:
                debug.logger & debug.flagBld and debug.logger(
                    f"loadModule: read {modName} from {mibSource} failed: {e}"
                )
                continue

            candidates.append((mibSource, codeObj, sfx))

        if len(candidates) < 2:
            return candidates

        revisions = [revisionOf(codeObj) for _, codeObj, _ in candidates]

        if not all(revisions) or len(set(revisions)) == 1:
            debug.logger & debug.flagBld and debug.logger(
                f"loadModule: {modName} left in source order; revisions {revisions}"
            )
            return candidates

        # Stable, so candidates sharing the newest revision keep the order
        # they were searched in.
        ordered = sorted(
            zip(revisions, candidates), key=lambda pair: pair[0] or "", reverse=True
        )

        debug.logger & debug.flagBld and debug.logger(
            f"loadModule: {modName} resolved by newest revision {ordered[0][0]}"
        )

        return [candidate for _, candidate in ordered]

    def loadModule(self, modName: str, **userCtx: Any) -> Any:
        """Load and execute MIB modules as Python code"""
        for mibSource, codeObj, sfx in self._candidates(modName):
            modPath = mibSource.fullPath(modName, sfx)

            if modPath in self.__modPathsSeen:
                debug.logger & debug.flagBld and debug.logger(
                    f"loadModule: seen {modPath}"
                )
                break

            else:
                self.__modPathsSeen.add(modPath)

            debug.logger & debug.flagBld and debug.logger(
                f"loadModule: evaluating {modPath}"
            )

            g = {"mibBuilder": self, "userCtx": userCtx}

            try:
                # Executing the MIB module is what loading one means: a pysnmp
                # MIB is Python that calls back into this builder.
                exec(codeObj, g)  # noqa: S102

            except Exception as e:
                self.__modPathsSeen.remove(modPath)
                raise error.MibLoadError(
                    f"MIB module '{modPath}' load error: {traceback.format_exception(type(e), e, e.__traceback__)}"
                ) from e

            self.__modSeen[modName] = modPath

            debug.logger & debug.flagBld and debug.logger(
                f"loadModule: loaded {modPath}"
            )

            break

        if modName not in self.__modSeen:
            raise error.MibNotFoundError(
                'MIB file "{}" not found in search path ({})'.format(
                    modName and modName + ".py[co]",
                    ", ".join([str(x) for x in self.__mibSources]),
                )
            )

        return self

    def loadModules(self, *modNames: str, **userCtx: Any) -> Any:
        """Load (optionally, compiling) pysnmp MIB modules"""
        # Build a list of available modules. A dict rather than a set: it
        # de-duplicates across sources while keeping the order they were
        # searched in.
        names = modNames
        if not names:
            found: dict[str, None] = {}
            for mibSource in self.__mibSources:
                for modName in mibSource.listdir():
                    found[modName] = None
            names = tuple(found)

        if not names:
            raise error.MibNotFoundError(f"No MIB module to load at {self}")

        for modName in names:
            try:
                self.loadModule(modName, **userCtx)

            except error.MibNotFoundError as exc:
                if self.__mibCompiler:
                    debug.logger & debug.flagBld and debug.logger(
                        f"loadModules: calling MIB compiler for {modName}"
                    )
                    status = self.__mibCompiler.compile(
                        modName, genTexts=self.loadTexts
                    )
                    errs = "; ".join(
                        [
                            hasattr(x, "error") and str(x.error) or x
                            for x in status.values()
                            if x in ("failed", "missing")
                        ]
                    )
                    if errs:
                        raise error.MibNotFoundError(
                            f"{modName} compilation error(s): {errs}"
                        ) from exc

                    # compilation succeeded, MIB might load now
                    self.loadModule(modName, **userCtx)

        return self

    def unloadModules(self, *modNames: str) -> Any:
        # Snapshot, since the loop mutates mibSymbols as it goes.
        names = modNames or tuple(self.mibSymbols)
        for modName in names:
            if modName not in self.mibSymbols:
                raise error.MibNotFoundError(f"No module {modName} at {self}")
            self.unexportSymbols(modName)
            self.__modPathsSeen.remove(self.__modSeen[modName])
            del self.__modSeen[modName]

            debug.logger & debug.flagBld and debug.logger(f"unloadModules: {modName}")

        return self

    def importSymbols(
        self, modName: str, *symNames: str, **userCtx: Any
    ) -> tuple[Any, ...]:
        if not modName:
            raise error.SmiError("importSymbols: empty MIB module name")
        r: tuple[Any, ...] = ()
        for symName in symNames:
            if modName not in self.mibSymbols:
                self.loadModules(modName, **userCtx)
            if modName not in self.mibSymbols:
                raise error.MibNotFoundError(f"No module {modName} loaded at {self}")
            if symName not in self.mibSymbols[modName]:
                raise error.SmiError(f"No symbol {modName}::{symName} at {self}")
            r = r + (self.mibSymbols[modName][symName],)
        return r

    def exportSymbols(
        self, modName: str, *anonymousSyms: Any, **namedSyms: Any
    ) -> None:
        if modName not in self.mibSymbols:
            self.mibSymbols[modName] = {}
        mibSymbols = self.mibSymbols[modName]

        for symObj in anonymousSyms:
            debug.logger & debug.flagBld and debug.logger(
                f"exportSymbols: anonymous symbol {modName}::__pysnmp_{self._autoName}"
            )
            mibSymbols[f"__pysnmp_{self._autoName}"] = symObj
            self._autoName += 1
        for symName, symObj in namedSyms.items():
            if symName in mibSymbols:
                raise error.SmiError(f"Symbol {symName} already exported at {modName}")

            if symName != self.moduleID and not isinstance(symObj, classTypes):
                label = symObj.getLabel()
                if label:
                    symName = label
                else:
                    symObj.setLabel(symName)

            mibSymbols[symName] = symObj

            debug.logger & debug.flagBld and debug.logger(
                f"exportSymbols: symbol {modName}::{symName}"
            )

        self.lastBuildId += 1

    def unexportSymbols(self, modName: str, *symNames: str) -> None:
        if modName not in self.mibSymbols:
            raise error.SmiError(f"No module {modName} at {self}")
        mibSymbols = self.mibSymbols[modName]
        # Snapshot, since the loop deletes from mibSymbols as it goes.
        names = symNames or tuple(mibSymbols)
        for symName in names:
            if symName not in mibSymbols:
                raise error.SmiError(f"No symbol {modName}::{symName} at {self}")
            del mibSymbols[symName]

            debug.logger & debug.flagBld and debug.logger(
                f"unexportSymbols: symbol {modName}::{symName}"
            )

        if not self.mibSymbols[modName]:
            del self.mibSymbols[modName]

        self.lastBuildId += 1
