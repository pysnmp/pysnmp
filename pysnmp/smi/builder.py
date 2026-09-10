#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""Loading MIB modules from wherever they are: a directory, a package, a corpus.

`MibBuilder` finds a module by name, imports it, applies any hand-written
runtime behavior from `pysnmp.smi.mibs.behavior`, and holds the symbols it
defined. A source is a directory or an importable package; a module is Python
rendered from ASN.1.
"""

import dis
import enum
import importlib
import importlib.machinery
import importlib.util
import marshal
import os
import struct
import time
import traceback
import warnings
from errno import ENOENT
from typing import Any, cast

from pysnmp import debug
from pysnmp import version as pysnmp_version
from pysnmp.error import PySnmpShadowedModuleWarning
from pysnmp.smi import error
from pysnmp.smi.mibs import behavior

PY_MAGIC_NUMBER = importlib.util.MAGIC_NUMBER
SOURCE_SUFFIXES = importlib.machinery.SOURCE_SUFFIXES
BYTECODE_SUFFIXES = importlib.machinery.BYTECODE_SUFFIXES

PY_SUFFIXES = SOURCE_SUFFIXES + BYTECODE_SUFFIXES

classTypes = (type,)


class MibSourceKind(str, enum.Enum):
    """What kind of place a module came from.

    A caller asking where a symbol came from is usually asking one of two
    questions -- is this still resolving out of the wheel, or has my corpus
    taken over; and did this come from the copy I installed or the one the
    framework ships -- and neither is answerable from a path alone. Two
    directories look the same, and the package a wheel unpacks to looks like
    any other directory.

    A ``str`` enum so that a value logs, compares and serializes as its own
    name without a caller having to import this to read it.
    """

    #: `pysnmp.smi.mibs` and `pysnmp.smi.mibs.instances` -- the modules the
    #: engine itself needs, searched first so nothing can displace them.
    OVERRIDE = "override"

    #: `pysmi.mibs.pysnmp`, the modules generated into the wheel pysnmp
    #: depends on. Searched last.
    WHEEL = "wheel"

    #: A plain directory of generated modules, registered by a caller.
    DIR = "dir"

    #: An importable package of generated modules, `PYSNMP_MIB_PKGS` included.
    PKG = "pkg"

    #: A corpus database, from `PYSNMP_MIB_DBS` or `setMibCorpus()`.
    DB = "db"

    #: Rendered on demand by an attached compiler, into its output directory.
    COMPILED = "compiled"


#: How to report a module found in more than one source.
#:
#: ``warn`` is the default because shadowing is a configuration a deployment
#: may well intend -- a local copy of a vendor MIB, deliberately placed ahead
#: of the bundled one. ``error`` is the setting for a deployment that has
#: finished migrating off `.py` and wants any surviving copy to be fatal;
#: ``silent`` for one that has decided to live with it.
CONFLICT_SEVERITIES = ("warn", "error", "silent")

#: The one shadowing pysnmp arranges itself, and so does not report.
#:
#: `defaultCoreMibs` exists to be searched ahead of `defaultGeneratedMibs`:
#: pysnmp carries its own copy of the seven modules the engine needs and the
#: wheel carries them too. Every stock install is therefore shadowing seven
#: modules before a caller has configured anything, and warning about it would
#: mean the default install warns -- which is both noise and a broken promise,
#: since nothing about that install has changed.
#:
#: Any other combination is the caller's doing and is reported. A local
#: directory shadowing the wheel is reported; a corpus shadowing an override
#: is reported.
FRAMEWORK_SHADOW = frozenset({MibSourceKind.OVERRIDE, MibSourceKind.WHEEL})


class __AbstractMibSource:
    #: What a source of this class is, absent anything more specific from the
    #: caller. `MibBuilder` overrides it for the sources it registers itself,
    #: which are packages by class and something more particular by intent.
    defaultKind: MibSourceKind = MibSourceKind.DIR

    def __init__(
        self,
        srcName: str,
        kind: "MibSourceKind | None" = None,
        sourceId: str | None = None,
    ) -> None:
        """Records where to look. Nothing is read until `init()`.

        Args:
            srcName: the directory or importable package to search
            kind: what this source is, for provenance. Defaults to what the
                class is, which is the right answer for a caller registering
                a directory or a package of their own
            sourceId: a stable name for this source, defaulting to *srcName*.
                Given separately because `ZipMibSource.init` rewrites
                `_srcName` to a path inside the archive, and provenance has to
                keep naming what the caller registered
        """
        self._srcName = srcName
        self._sourceId = srcName if sourceId is None else sourceId
        self.mibSourceKind = self.defaultKind if kind is None else kind
        self.__inited = None
        debug.logger & debug.flagBld and debug.logger(f"trying {self}")

    @property
    def sourceId(self) -> str:
        """A stable name for this source, as the caller named it."""
        return self._sourceId

    @property
    def provenance(self) -> "tuple[MibSourceKind, str]":
        """What this source is and which one it is, as provenance records it."""
        return self.mibSourceKind, self._sourceId

    def __repr__(self) -> str:
        """The source and where it points, for debug logging."""
        return f"{self.__class__.__name__}({self._srcName!r})"

    def _uniqNames(self, names: list[str]) -> tuple[str, ...]:
        """Module names from filenames, with the suffixes stripped and duplicates gone.

        One module shows up once as `.py` and again as `.pyc`, and `__init__` is not a
        MIB module at all.
        """
        u: set[str] = set()

        for f in names:
            if f.startswith("__init__."):
                continue

            u.update(f[: -len(sfx)] for sfx in PY_SUFFIXES if f.endswith(sfx))

        return tuple(u)

    # MibSource API follows

    def fullPath(self, *args: Any) -> str:
        """Where a module would live in this source, whether or not it is there."""
        f = args[0] if args else ""
        sfx = args[1] if len(args) > 1 else ""
        return self._srcName + (f and (os.sep + f + sfx) or "")

    def init(self) -> Any:
        """Open the source, returning self or another source to use in its place.

        A source may find at open time that something else should serve it -- a zip
        source pointed at an ordinary install being the case that matters, since a
        wheel unpacks to a directory -- so it can hand back a substitute rather than
        fail. Opening twice is a no-op.
        """
        if self.__inited is None:
            self.__inited = self._init()
            if self.__inited is self:
                self.__inited = True
        if isinstance(self.__inited, bool) and self.__inited:
            return self

        else:
            return self.__inited

    def listdir(self) -> tuple[str, ...]:
        """The module names this source can supply."""
        return self._listdir()

    def read(self, f: str) -> Any:
        """The compiled module named ``f``, with the suffix it was found under.

        Prefers a ``.pyc`` when one is present and no older than the source,
        and falls back to compiling the ``.py``. Returns ``(code, suffix)`` --
        the suffix rather than a path, because the caller composes the module's
        location itself with ``fullPath(modName, sfx)``.

        Raises ``OSError(ENOENT)`` when neither form of the module is present,
        and ``error.MibLoadError`` when one is present but unreadable.
        """
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
            # The suffix, to match the bytecode branch above. `_getData` hands
            # back a full path, and returning that made `loadModule` compose
            # `fullPath(modName, sfx)` out of a directory, a module name and a
            # second absolute path -- unique per source and module, so dedup
            # worked, but never a path. It reached every `MibLoadError`, and
            # now `getModulePath` answers with it.
            return compile(modData, pyPath, "exec"), pySfx

        raise OSError(ENOENT, "No suitable module found", f)

    # Interfaces for subclasses
    def _init(self) -> Any:
        """Open the source. Concrete sources implement this."""
        raise NotImplementedError

    def _listdir(self) -> tuple[str, ...]:
        """List module names. Concrete sources implement this."""
        raise NotImplementedError

    def _getTimestamp(self, f: str) -> float:
        """When a file was last written. Concrete sources implement this."""
        raise NotImplementedError

    def _getData(self, f: str, mode: str) -> tuple[Any, str]:
        """Read a file, returning its content and path. Concrete sources implement this."""
        raise NotImplementedError


class ZipMibSource(__AbstractMibSource):
    """MIB modules loaded out of a zip archive, including an egg or a wheel."""

    defaultKind = MibSourceKind.PKG

    # zipimport.zipimporter carries the archive directory privately, and
    # typeshed describes neither it nor the loader `__import__` hands back, so
    # there is nothing narrower to say here than what `_archiveFiles` checks.
    __loader: Any

    @staticmethod
    def _archiveFiles(loader: Any) -> Any:
        """The archive directory, under whichever name this Python has for it.

        `zipimporter` exposed it as `_files` until Python 3.14 replaced that
        with `_get_files()`. Both are private, and neither has a public
        equivalent -- the loader offers no way to list an archive's members --
        but without one a zip-installed MIB package cannot be enumerated at
        all, so it is read rather than done without.

        Returns
        -------
            The mapping of member path to archive entry, or ``None`` for a
            loader that is not a zipimporter.
        """
        if hasattr(loader, "_get_files"):
            return loader._get_files()

        return getattr(loader, "_files", None)

    def _init(self) -> Any:
        """Resolve ``_srcName`` to whichever source can actually serve it.

        A package name names a zip source only when the interpreter imported it
        through ``zipimporter``. An ordinary install is a directory -- which is
        what a wheel unpacks to -- so this hands back a ``DirMibSource`` for
        both the installed and the relative-to-CWD case, and answers with
        itself only for a genuine archive.

        A substitute carries this source's kind and id rather than taking a
        directory's: which of them serves a package is an installation detail,
        and provenance that changed with it would report `dir` for the same
        wheel a zip install reports `wheel` for.
        """
        try:
            p = __import__(self._srcName, globals(), locals(), ["__init__"])
            if (
                hasattr(p, "__loader__")
                and self._archiveFiles(p.__loader__) is not None
            ):
                self.__loader = p.__loader__
                self._srcName = self._srcName.replace(".", os.sep)
                return self
            elif getattr(p, "__file__", None):
                # Dir relative to PYTHONPATH. __file__ is Optional -- a
                # namespace package has none -- but the guard above has
                # already established this one has a path.
                return DirMibSource(
                    os.path.split(cast(str, p.__file__))[0],
                    kind=self.mibSourceKind,
                    sourceId=self._sourceId,
                ).init()
            else:
                raise error.MibLoadError(f"{p} access error")

        except ImportError:
            # Dir relative to CWD
            return DirMibSource(
                self._srcName, kind=self.mibSourceKind, sourceId=self._sourceId
            ).init()

    def fullPath(self, *args: Any) -> str:
        """Qualify the archive member with the archive it lives in.

        ``_init`` rewrites ``_srcName`` to the member path -- ``pysmi/mibs/
        pysnmp`` -- which on its own names no file on disk and is ambiguous
        between two archives holding the same package. Prefixing the archive
        makes it locate the module, and makes it comparable with what
        ``importlib`` reports for the same package.
        """
        archive = getattr(self.__loader, "archive", "")

        return (
            os.path.join(archive, super().fullPath(*args))
            if archive
            else super().fullPath(*args)
        )

    @staticmethod
    def _parseDosTime(dosdate: int, dostime: int) -> float:
        """Convert a zip entry's DOS date and time into a Unix timestamp.

        Zip stores modification time in the packed MS-DOS format, which is what the
        staleness check between a `.pyc` and its `.py` has to compare against.
        """
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
        """The module names the archive holds directly under ``_srcName``.

        The archive directory is flat and keyed by full member path, so a
        member belongs to this source only when its directory part matches
        exactly -- a nested package is not a member of its parent here.
        """
        names = []
        # noinspection PyProtectedMember
        for f in self._archiveFiles(self.__loader):
            d, f = os.path.split(f)
            if d == self._srcName:
                names.append(f)
        return tuple(self._uniqNames(names))

    def _getTimestamp(self, f: str) -> float:
        """The archive member's modification time, as a Unix timestamp.

        A zip records the DOS date and time fields its directory carries rather
        than a Unix timestamp, so ``_parseDosTime`` converts them. Raises
        ``OSError(ENOENT)`` when the archive holds no such member, which is
        what ``read`` reads as "this form of the module is absent".
        """
        p = os.path.join(self._srcName, f)
        # noinspection PyProtectedMember
        files = self._archiveFiles(self.__loader)
        if p in files:
            return self._parseDosTime(files[p][6], files[p][5])
        else:
            raise OSError(ENOENT, "No such file in ZIP archive", p)

    def _getData(self, f: str, mode: str | None = None) -> tuple[Any, str]:
        """Read one archive member."""
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
    """MIB modules loaded out of a filesystem directory."""

    def _init(self) -> Any:
        """Normalize the path. There is nothing to open until a module is asked for."""
        self._srcName = os.path.normpath(self._srcName)
        return self

    def _listdir(self) -> tuple[str, ...]:
        """The module names in the directory, or nothing where it cannot be read.

        A MIB path routinely names directories that do not exist, so an unreadable one
        is logged and skipped rather than raised -- the other sources may well have the
        module.
        """
        try:
            return self._uniqNames(os.listdir(self._srcName))
        except OSError as why:
            debug.logger & debug.flagBld and debug.logger(
                f"listdir() failed for {self._srcName}: {why}"
            )
            return ()

    def _getTimestamp(self, f: str) -> float:
        """When a file was last written."""
        p = os.path.join(self._srcName, f)
        try:
            return os.stat(p)[8]
        except OSError as e:
            raise OSError(ENOENT, f"No such file: {e}", p) from e

    def _getData(self, f: str, mode: str) -> tuple[Any, str]:
        """Read one file, matching the name case-sensitively.

        The directory listing is consulted rather than the file opened directly,
        because MIB module names are case-sensitive and the filesystem may not be.
        """
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

    Returns
    -------
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
    """Loads MIB modules and holds the symbols they define.

    A module is searched for across every registered source, and where more than
    one source has it, the copy stating the newest MODULE-IDENTITY revision wins;
    search order settles only what the revisions cannot. Loading a module loads
    what it IMPORTS first, so asking for one symbol can pull in a graph of them.
    """

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

    #: What to do about a module more than one source carries: ``warn``,
    #: ``error`` or ``silent``, from `CONFLICT_SEVERITIES`.
    #:
    #: Shared with the compiler's own idea of severity in the sense that it
    #: answers the same question -- a deployment part-way through migrating off
    #: generated `.py` wants to see what is still shadowed, and one that has
    #: finished wants any survivor to be fatal.
    moduleConflictSeverity = "warn"

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
        """Assemble the search path, in the order modules are looked for.

        The environment comes first (`PYSNMP_MIB_PKGS`, `PYSNMP_MIB_DIRS`,
        `PYSNMP_MIB_DIR`), then the core modules, which are inserted at the front so
        nothing overrides the ones the engine itself needs, then the generated ones.
        That ordering is what lets a user's copy of a MIB shadow the bundled one
        without being able to displace the framework modules.

        `PYSNMP_MIB_DBS` names corpora rather than sources and so is handled
        separately, at the end: a corpus is searched only where the sources
        come up empty, which is what keeps configuring one from changing any
        answer a deployment already had.

        Raises
        ------
            SmiError: `PYSNMP_MIB_DBS` names something that is not a readable
                corpus.
        """
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
            sources.insert(0, ZipMibSource(m, kind=MibSourceKind.OVERRIDE))
        if self.defaultGeneratedMibs:
            for m in self.defaultGeneratedMibs.split(os.pathsep):
                sources.append(ZipMibSource(m, kind=MibSourceKind.WHEEL))
        self.mibSymbols: dict[str, dict[str, Any]] = {}
        self.__mibSources: list[MibSource] = []
        self.__modSeen: dict[str, str] = {}
        self.__modPathsSeen: set[str] = set()
        self.__modProvenance: dict[str, tuple[MibSourceKind, str]] = {}
        self.__mibCompiler: Any = None
        self.__mibCorpus: Any = None
        self.__corpusBuilding: set[str] = set()
        self.__shadowsReported = False
        self.setMibSources(*sources)

        # Imported here rather than at module scope so that the default path
        # -- no corpus configured, which is every existing deployment -- does
        # not pay for sqlite3.
        dbs = [x for x in os.environ.get("PYSNMP_MIB_DBS", "").split(os.pathsep) if x]

        if dbs:
            from pysnmp.smi.corpus import open_corpora

            self.setMibCorpus(open_corpora(dbs))

    # MIB corpus management

    def getMibCorpus(self) -> Any:
        """The corpus this builder falls back to, or ``None``.

        Returns
        -------
            The :py:class:`~pysnmp.smi.corpus.MibCorpus`, or ``None`` when
            none is configured -- which is the default and means this builder
            resolves exactly as it always has.
        """
        return self.__mibCorpus

    def setMibCorpus(self, mibCorpus: Any) -> Any:
        """Resolve from a corpus what the MIB sources do not carry.

        A corpus is a SQLite database pysmi produces, holding the SMI model as
        data rather than as Python. Configuring one **adds a place to look**;
        it does not replace the MIB sources, reorder them, or change what a
        module already on disk resolves to. A module found by the ordinary
        search is loaded the ordinary way, so an existing deployment that
        configures a corpus keeps every answer it had and gains answers for
        the modules it did not ship.

        That ordering is the whole compatibility story, and it is deliberate:
        the corpus is where a module is found when nothing else has it, which
        is what makes this opt-in rather than a migration.

        Args:
            mibCorpus: an open
                :py:class:`~pysnmp.smi.corpus.MibCorpus`, a
                :py:class:`~pysnmp.smi.corpus.CompositeMibCorpus` over several
                of them, or ``None`` to stop using one. `PYSNMP_MIB_DBS` is a
                thin layer over this: it opens the corpora it names, in the
                order it names them, and calls this.

        Returns
        -------
            This builder.
        """
        self.__mibCorpus = mibCorpus
        self.__shadowsReported = False

        return self

    def _corpusMayAnswer(self) -> bool:
        """Whether the corpus may build the next module, given ``loadTexts``.

        A corpus carries no DESCRIPTION and no REFERENCE, so it cannot satisfy
        ``loadTexts``. What that should mean depends on whether anything else
        can. A compiler renders ASN.1 with ``genTexts``, so declining leaves
        the module to fall through to it and come back with its prose intact --
        which is the whole point of running both: the corpus answers the many
        modules cheaply, the compiler answers the few a caller wants to read.

        With no compiler there is nothing to fall through to, and a caller that
        asked for descriptions and got a module with none cannot tell that from
        a MIB declaring none. That case is refused outright.

        Decided here rather than once at attachment. ``loadTexts`` is a plain
        attribute a caller may set at any time, and a compiler may be attached
        after the corpus is, so an answer computed at ``setMibCorpus()`` would
        depend on the order the two were configured in.

        Returns
        -------
            Whether the corpus should be asked for the module.

        Raises
        ------
            SmiError: texts were asked for, the corpus has none, and no
                compiler is configured to render them.
        """
        if not self.loadTexts or getattr(self.__mibCorpus, "loadTexts", False):
            return True

        if self.__mibCompiler is not None:
            debug.logger & debug.flagBld and debug.logger(
                f"_corpusMayAnswer: corpus at {self.__mibCorpus} carries no "
                f"texts, leaving the module to the compiler"
            )
            return False

        raise error.SmiError(
            f"loadTexts is set but the corpus at {self.__mibCorpus} carries no "
            f"texts; attach a MIB compiler to render descriptions from ASN.1, "
            f"read them from the published json/ tree, or clear loadTexts"
        )

    def _loadModuleFromCorpus(self, modName: str) -> bool:
        """Build a module out of the corpus, if one is configured and has it.

        Args:
            modName: the module to build

        Returns
        -------
            Whether it was built.
        """
        if self.__mibCorpus is None:
            return False

        # Declining under loadTexts is how the module reaches the compiler:
        # loadModule() raises MibNotFoundError when nothing built it, which is
        # what loadModules() catches to compile with genTexts.
        if not self._corpusMayAnswer():
            return False

        if modName in self.__corpusBuilding:
            # A module reached again while it is being built. Synthesis
            # resolves imported types through importSymbols, which comes back
            # here, so an import cycle -- A imports from B, B from A -- would
            # otherwise recurse without limit. It cannot be caught by
            # __modSeen: synthesis exports into mibSymbols only once it
            # finishes, so marking the module loaded up front would make the
            # re-entrant importSymbols raise MibNotFoundError instead.
            from pysnmp.smi.corpus import MibCorpusCycleError

            raise MibCorpusCycleError(
                f"MIB module {modName} is being built from the corpus and was "
                f"asked for again; its imports form a cycle"
            )

        from pysnmp.smi import synthesis

        self.__corpusBuilding.add(modName)

        try:
            built = synthesis.load_module(self, self.__mibCorpus, modName)

        finally:
            self.__corpusBuilding.discard(modName)

        if not built:
            return False

        # Recorded under a path no MIB source can produce, so that
        # unloadModules() and the already-loaded check treat a synthesized
        # module exactly like a loaded one.
        self.__modSeen[modName] = f"corpus:{self.__mibCorpus.path}/{modName}"
        self.__modPathsSeen.add(self.__modSeen[modName])

        # Which corpus, not which composite: a module resolves from exactly
        # one, and naming the whole search path would make provenance unable
        # to tell a distro corpus from a customer one, which is most of what
        # it is for.
        owner = getattr(self.__mibCorpus, "owner", None)
        carrier = owner(modName) if owner else None

        self.__modProvenance[modName] = (
            MibSourceKind.DB,
            getattr(carrier, "path", self.__mibCorpus.path),
        )

        debug.logger & debug.flagBld and debug.logger(
            f"loadModule: {modName} built from corpus {self.__mibCorpus.path}"
        )

        return True

    # MIB compiler management

    def getMibCompiler(self) -> Any:
        """The compiler that renders ASN.1 on demand, or `None` where none is set."""
        return self.__mibCompiler

    def setMibCompiler(self, mibCompiler: Any, destDir: str) -> Any:
        """Attach a compiler and add its output directory as a source.

        Adding the source is the point: a module the compiler renders has to be
        loadable afterwards, and nothing else would put that directory on the path.
        """
        self.addMibSources(DirMibSource(destDir, kind=MibSourceKind.COMPILED))
        self.__mibCompiler = mibCompiler
        return self

    # MIB modules management

    def addMibSources(self, *mibSources: Any) -> None:
        """Add sources to search, opening each one."""
        self.__mibSources.extend([s.init() for s in mibSources])
        self.__shadowsReported = False
        debug.logger & debug.flagBld and debug.logger(
            f"addMibSources: new MIB sources {self.__mibSources}"
        )

    def setMibSources(self, *mibSources: Any) -> None:
        """Replace the sources to search, opening each one."""
        self.__mibSources = [s.init() for s in mibSources]
        self.__shadowsReported = False
        debug.logger & debug.flagBld and debug.logger(
            f"setMibSources: new MIB sources {self.__mibSources}"
        )

    def getMibSources(self) -> tuple[Any, ...]:
        """The sources currently searched."""
        return tuple(self.__mibSources)

    def getModulePath(self, modName: str) -> str | None:
        """Where a loaded module came from, or ``None`` if it is not loaded.

        Which source answered is not decoration now that more than one can:
        the same name may be present in several, and best match decides. A
        caller -- or a test -- wanting to know which copy it got had no way to
        ask.
        """
        return self.__modSeen.get(modName)

    def getModuleProvenance(self, modName: str) -> "tuple[MibSourceKind, str] | None":
        """What kind of source a loaded module came from, and which one.

        `getModulePath` answers with a path, which is what a person reads and
        not what a program can act on: a wheel and a directory of overrides are
        both directories, and a corpus is not a path in the sense the others
        are. This answers ``(kind, source_id)`` instead -- the kind for
        deciding, the id for telling two sources of that kind apart, a distro
        corpus from a customer one above all.

        Tracked per module rather than per node. One module resolves from one
        source, so a per-node record would be the same answer repeated once per
        OID: on the order of a thousand entries either way against several
        hundred thousand.

        Args:
            modName: the module, as it was loaded

        Returns
        -------
            The pair, or ``None`` for a module that is not loaded. A module
            that was unloaded is not loaded.
        """
        return self.__modProvenance.get(modName)

    def __corporaInPlay(self) -> "tuple[Any, ...]":
        """The corpora configured, flattened out of a composite if it is one."""
        if self.__mibCorpus is None:
            return ()

        return tuple(getattr(self.__mibCorpus, "corpora", (self.__mibCorpus,)))

    def shadowedModules(self) -> "dict[str, list[tuple[MibSourceKind, str]]]":
        """Modules more than one source can supply, and which sources those are.

        Name-level only, and deliberately: answering whether two copies of a
        module differ means reading and normalizing both, which is the work a
        corpus exists to avoid. So this reports *shadowing* -- that a second
        copy exists and will be passed over -- and never claims the copies are
        equal or that they differ.

        Sources in the order `_candidates` searches them, then the corpora.
        That is not the winning order: revision decides among sources, and
        reading it means reading every candidate module, which is the cost
        this avoids. A caller wanting the copy that actually won asks
        `getModuleProvenance` once the module is loaded.

        Returns
        -------
            Module name to the sources carrying it, for the modules more than
            one source carries. Empty when nothing is shadowed.
        """
        carriers: dict[str, list[tuple[MibSourceKind, str]]] = {}

        for mibSource in self.__mibSources:
            for modName in mibSource.listdir():
                carriers.setdefault(modName, []).append(mibSource.provenance)

        for corpus in self.__corporaInPlay():
            for modName in corpus.modules():
                carriers.setdefault(modName, []).append((MibSourceKind.DB, corpus.path))

        return {modName: found for modName, found in carriers.items() if len(found) > 1}

    def reportShadowedModules(self) -> "dict[str, list[tuple[MibSourceKind, str]]]":
        """Report every shadowed module once, at the configured severity.

        Enumerating every source is the cost, and `loadModules()` called with
        no names already pays it, so that is the path that calls this. A caller
        who loads modules by name and still wants the report calls it directly.

        Reported once per builder, so a program that loads modules in several
        passes does not emit the same lines each time. `addMibSources`,
        `setMibSources` and `setMibCorpus` arm it again, since any of them can
        create a collision that did not exist before.

        `FRAMEWORK_SHADOW` is left out -- pysnmp's own copies of the engine
        modules shadowing the wheel's is what the search order is for, and a
        stock install would otherwise warn seven times having configured
        nothing. `shadowedModules` still reports it, being a question about
        the sources rather than about the configuration.

        Raises
        ------
            SmiError: `moduleConflictSeverity` is ``error`` and something is
                shadowed, or it is not one of `CONFLICT_SEVERITIES`.

        Returns
        -------
            What `shadowedModules` returned, so a caller can act on it without
            enumerating a second time.
        """
        if self.moduleConflictSeverity not in CONFLICT_SEVERITIES:
            raise error.SmiError(
                f"moduleConflictSeverity is {self.moduleConflictSeverity!r}, "
                f"expected one of {', '.join(CONFLICT_SEVERITIES)}"
            )

        shadowed = {
            modName: found
            for modName, found in self.shadowedModules().items()
            if {kind for kind, _ in found} != FRAMEWORK_SHADOW
        }

        if self.__shadowsReported or not shadowed:
            self.__shadowsReported = True
            return shadowed

        self.__shadowsReported = True

        # Counted apart from the per-module lines. A deployment whose second
        # corpus mostly repeats the first is paying for both and getting one,
        # and at that scale the per-module lines are too many to read -- the
        # total is what makes it visible.
        overlapping = sum(
            1
            for found in shadowed.values()
            if sum(1 for kind, _ in found if kind is MibSourceKind.DB) > 1
        )

        for modName, found in sorted(shadowed.items()):
            first, *rest = found
            line = (
                f"{modName} is carried by {len(found)} sources: "
                f"{first[0].value}:{first[1]} is searched first, shadowing "
                + ", ".join(f"{kind.value}:{name}" for kind, name in rest)
            )

            debug.logger & debug.flagBld and debug.logger(
                f"reportShadowedModules: {line}"
            )

            if self.moduleConflictSeverity == "warn":
                warnings.warn(line, PySnmpShadowedModuleWarning, stacklevel=2)

        if overlapping:
            debug.logger & debug.flagBld and debug.logger(
                f"reportShadowedModules: {overlapping} modules are carried by "
                f"more than one corpus"
            )

        if self.moduleConflictSeverity == "error":
            raise error.SmiError(
                f"{len(shadowed)} MIB modules are carried by more than one "
                f"source: {', '.join(sorted(shadowed))}"
            )

        return shadowed

    # Legacy/compatibility methods (won't work for .eggs)
    def setMibPath(self, *mibPaths: str) -> None:
        """Replace the sources with plain directories, for callers that predate sources."""
        self.setMibSources(*[DirMibSource(x) for x in mibPaths])

    def getMibPath(self) -> tuple[str, ...]:
        """The sources as directory paths. Raises where any source is not a directory."""
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
        """Load and execute MIB modules as Python code."""
        if modName in self.__modSeen:
            # Already loaded, and loading is not idempotent: a MIB registers
            # its symbols as it runs, so executing a second copy over the first
            # raises out of `exportSymbols` on the first symbol they share.
            #
            # This became reachable when selection stopped following source
            # order. Before, a source added after the fact was appended, so the
            # copy already loaded was still found first and the `modPathsSeen`
            # check below caught it. Best match will now put a newer copy
            # ahead of it, and a newer copy is a different path.
            #
            # Picking up a replacement therefore means `unloadModules()` first,
            # which is what it meant before as well.
            return self

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

                # Then whatever the ASN.1 could not state. Run in the module's
                # own globals, after it built its objects, so a fragment reads
                # and writes the symbols the module just defined -- see
                # pysnmp.smi.mibs.behavior. Inside the try because a failing
                # fragment leaves the module half-built exactly as a failing
                # module body does, and should be reported the same way.
                if behavior.apply(modName, g):
                    debug.logger & debug.flagBld and debug.logger(
                        f"loadModule: applied behavior for {modName}"
                    )

            except Exception as e:
                self.__modPathsSeen.remove(modPath)
                raise error.MibLoadError(
                    f"MIB module '{modPath}' load error: {traceback.format_exception(type(e), e, e.__traceback__)}"
                ) from e

            self.__modSeen[modName] = modPath
            self.__modProvenance[modName] = mibSource.provenance

            debug.logger & debug.flagBld and debug.logger(
                f"loadModule: loaded {modPath}"
            )

            break

        if modName not in self.__modSeen and not self._loadModuleFromCorpus(modName):
            raise error.MibNotFoundError(
                'MIB file "{}" not found in search path ({})'.format(
                    modName and modName + ".py[co]",
                    ", ".join([str(x) for x in self.__mibSources]),
                )
            )

        return self

    def loadModules(self, *modNames: str, **userCtx: Any) -> Any:
        """Load (optionally, compiling) pysnmp MIB modules."""
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

            # Enumerating every source is the whole cost of the shadow report
            # and this path has just paid it, so it is the one place the
            # report is free. Before loading anything, so that a deployment
            # configured to treat shadowing as fatal fails before it has half
            # a MIB set in memory.
            self.reportShadowedModules()

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
        """Unload modules, or every loaded module when given none.

        What was unloaded can be loaded again; the record of where it came from is
        dropped along with the symbols, so a second load searches afresh and may well
        find a different copy.
        """
        # Snapshot, since the loop mutates mibSymbols as it goes.
        names = modNames or tuple(self.mibSymbols)
        for modName in names:
            if modName not in self.mibSymbols:
                raise error.MibNotFoundError(f"No module {modName} at {self}")
            self.unexportSymbols(modName)
            self.__modPathsSeen.remove(self.__modSeen[modName])
            del self.__modSeen[modName]
            self.__modProvenance.pop(modName, None)

            debug.logger & debug.flagBld and debug.logger(f"unloadModules: {modName}")

        return self

    def importSymbols(
        self, modName: str, *symNames: str, **userCtx: Any
    ) -> tuple[Any, ...]:
        """Fetch symbols from a module, loading the module first if it is not loaded."""
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
        """Publish symbols under a module name, labelling those that have no label.

        A symbol whose label differs from the name it was passed under is filed by the
        label, since that is the name the MIB gives it and what a lookup will ask for.
        Anonymous symbols get a generated name so they can be unloaded later.
        """
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
        """Withdraw symbols, or the whole module when given none."""
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
