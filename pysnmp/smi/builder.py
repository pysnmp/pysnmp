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
from pysnmp.smi.mibs import behavior

PY_MAGIC_NUMBER = importlib.util.MAGIC_NUMBER
SOURCE_SUFFIXES = importlib.machinery.SOURCE_SUFFIXES
BYTECODE_SUFFIXES = importlib.machinery.BYTECODE_SUFFIXES

PY_SUFFIXES = SOURCE_SUFFIXES + BYTECODE_SUFFIXES

classTypes = (type,)


class __AbstractMibSource:
    def __init__(self, srcName: str) -> None:
        """Records where to look. Nothing is read until `init()`."""
        self._srcName = srcName
        self.__inited = None
        debug.logger & debug.flagBld and debug.logger(f"trying {self}")

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
                return DirMibSource(os.path.split(cast(str, p.__file__))[0]).init()
            else:
                raise error.MibLoadError(f"{p} access error")

        except ImportError:
            # Dir relative to CWD
            return DirMibSource(self._srcName).init()

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
            sources.insert(0, ZipMibSource(m))
        if self.defaultGeneratedMibs:
            for m in self.defaultGeneratedMibs.split(os.pathsep):
                sources.append(ZipMibSource(m))
        self.mibSymbols: dict[str, dict[str, Any]] = {}
        self.__mibSources: list[MibSource] = []
        self.__modSeen: dict[str, str] = {}
        self.__modPathsSeen: set[str] = set()
        self.__mibCompiler: Any = None
        self.__mibCorpus: Any = None
        self.__corpusBuilding: set[str] = set()
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

        Raises
        ------
            SmiError: ``loadTexts`` is set and the corpus carries no prose.
                Refused rather than silently satisfied: a caller that asked
                for descriptions and got a module with none has no way to
                tell that from a MIB that declares none.
        """
        self._checkCorpusTexts(mibCorpus)

        self.__mibCorpus = mibCorpus

        return self

    def _checkCorpusTexts(self, mibCorpus: Any) -> None:
        """Refuse a textless corpus while ``loadTexts`` asks for prose.

        Called both when a corpus is attached and again before each synthesis,
        because ``loadTexts`` is a plain attribute a caller may set at any
        time. Checking only at attachment would leave a builder that turned
        texts on afterwards silently building modules with none.

        Args:
            mibCorpus: the corpus about to be used, or ``None``

        Raises
        ------
            SmiError: texts were asked for and the corpus has none.
        """
        if (
            mibCorpus is not None
            and self.loadTexts
            and not getattr(mibCorpus, "loadTexts", False)
        ):
            raise error.SmiError(
                f"loadTexts is set but the corpus at {mibCorpus} carries no "
                f"texts; load descriptions from the published json/ tree, or "
                f"clear loadTexts"
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

        # Re-checked here, not only at setMibCorpus(). loadTexts is a plain
        # attribute, so setting it after a corpus is attached would otherwise
        # slip past the check and quietly build modules with no DESCRIPTION.
        self._checkCorpusTexts(self.__mibCorpus)

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
        self.addMibSources(DirMibSource(destDir))
        self.__mibCompiler = mibCompiler
        return self

    # MIB modules management

    def addMibSources(self, *mibSources: Any) -> None:
        """Add sources to search, opening each one."""
        self.__mibSources.extend([s.init() for s in mibSources])
        debug.logger & debug.flagBld and debug.logger(
            f"addMibSources: new MIB sources {self.__mibSources}"
        )

    def setMibSources(self, *mibSources: Any) -> None:
        """Replace the sources to search, opening each one."""
        self.__mibSources = [s.init() for s in mibSources]
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
