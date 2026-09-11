#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
# License: https://github.com/pysnmp/pysnmp/blob/main/LICENSE.rst
#
"""Reading a MIB corpus, and building MIB objects from its rows.

A corpus is a SQLite database pysmi produces -- ``core.db``, specified in
pysmi's ``corpus-schema`` document. It carries the SMI model as data: one row
per node, keyed for lookup by OID and by name and ordered for GETNEXT.

**Nothing here is on the default path.** A ``MibBuilder`` with no corpus
configured behaves exactly as it did: it searches its MIB sources, finds
generated Python, and executes it. Configuring a corpus adds a place to look
when that search comes up empty; it does not replace it, reorder it, or change
what a module already on disk resolves to. That is what lets an existing
deployment -- splunk-connect-for-snmp among them -- upgrade without changing
anything, and opt in when it wants to.

Why a corpus is worth opting into
---------------------------------

The published ``index-v2.csv`` already answers *which module owns this OID*, so
lazy loading needs no corpus. What it cannot answer is *what is the node at
this OID* -- it is ``MODULE,OID`` and carries anchors only, so a leaf like
``ifDescr`` is not in it -- or *what comes after this OID*, which an anchor
index has no ordering to answer at all.

Answering the first from the published ``json/`` tree means parsing a whole
module. Answering it from ASN.1 means running the compiler on the trap path.
Here both are one indexed row.

Reading, not writing
--------------------

pysmi owns the SMI model and every artifact shape; this repository owns the
runtime object shape. So the writer is there and the reader is here, and the
contract between them is a documented file format plus a conformance fixture
that runs in this repository's CI (pysnmp/pysnmp#196, pysnmp/pysnmp#199).

The consequence worth stating: **this module imports ``sqlite3`` and nothing
from pysmi.** A corpus is read with the standard library, which is what lets
pysmi be an optional dependency here rather than a deeper one.
"""

import json
import os
import sqlite3
import urllib.request
from typing import Any, Final, Union

from pysnmp.smi import error

__all__ = [
    "OBJECT_CLASSES",
    "TIERS",
    "CompositeMibCorpus",
    "MibCorpus",
    "MibCorpusCycleError",
    "best_by_corpus_rank",
    "best_by_revision",
    "oid_from_key",
    "oid_key",
    "open_corpora",
    "revision_rank",
    "subtree_bound",
]

#: Where a namespace ranks when two modules from different ones claim an arc,
#: best first. pysmi's ``namespace.TIERS``, which is where the order is
#: settled; repeated rather than imported because pysmi is optional and this
#: module is on the no-compiler path.
TIERS: Final[tuple[str, ...]] = ("standard", "draft", "vendor")

#: Node classes that count as objects when asking whether a module is wholly
#: obsolete. A module's registration points staying current while every object
#: under them is obsolete does not make it a live module. pysmi's
#: ``index.OBJECT_CLASSES``.
OBJECT_CLASSES: Final[tuple[str, ...]] = ("objecttype", "notificationtype")


class MibCorpusCycleError(error.SmiError):
    """A module was asked for again while being built from the corpus.

    Raised rather than recursed on: synthesis resolves imported types through
    ``importSymbols``, which comes back to ``loadModule``, so a corpus whose
    IMPORTS form a cycle would otherwise recurse without limit. It is its own
    class so that the type resolver can tell it apart from the ordinary "that
    module does not define this symbol", which it is allowed to recover from.
    """


#: The corpus schema this reader understands.
#:
#: A corpus stamps its own version in ``meta`` and in the file's
#: ``user_version`` header field. Refusing what we cannot read is deliberate:
#: reading the subset we recognize out of a newer corpus would resolve some
#: OIDs and silently not others.
SCHEMA_VERSION: Final = 1

#: SQLite's ``application_id`` for a corpus -- ``PSMI`` as big-endian ASCII.
#: Checked before any table is trusted, so pointing this at an unrelated
#: database is a clear error rather than a confusing one.
APPLICATION_ID: Final = 0x50534D49

#: Largest sub-identifier :py:func:`oid_key` encodes. RFC 2578 section 7.1.3
#: makes a sub-identifier a 32-bit unsigned integer.
MAX_ARC: Final = 0xFFFFFFFF


def oid_key(oid: Union[str, "tuple[int, ...]"]) -> bytes:
    """Encode an OID so that bytewise order is numeric order.

    Each arc becomes a length byte followed by that many big-endian bytes.
    Comparing two encodings compares the length bytes first, and a longer arc
    is a larger arc, so the order is right without padding every arc to four
    bytes. Two properties follow, and the corpus depends on both: an OID that
    is a prefix of another encodes to a byte prefix of it, so a subtree is a
    range; and a prefix sorts before everything under it, so ``oid_key > ?``
    ascending is GETNEXT.

    This is pysmi's encoding, reimplemented rather than imported. It is twenty
    lines, and importing pysmi to read a file whose whole point is that it can
    be read without pysmi would defeat the exercise.

    Args:
        oid: dotted decimal, or arcs as integers

    Returns
    -------
        The sort key.

    Raises
    ------
        SmiError: the OID is not one, or an arc is out of range.
    """
    if isinstance(oid, str):
        try:
            arcs = tuple(int(x) for x in oid.split("."))

        except ValueError:
            raise error.SmiError(f"not an OID: {oid!r}") from None

    else:
        arcs = tuple(oid)

    if not arcs:
        raise error.SmiError("empty OID")

    out = bytearray()

    for arc in arcs:
        if arc < 0 or arc > MAX_ARC:
            raise error.SmiError(f"sub-identifier out of range in {oid!r}: {arc}")

        width = max(1, (arc.bit_length() + 7) // 8)
        out.append(width)
        out += arc.to_bytes(width, "big")

    return bytes(out)


def oid_from_key(key: bytes) -> str:
    """Decode what :py:func:`oid_key` encoded.

    Args:
        key: the sort key

    Returns
    -------
        The OID, dotted decimal.

    Raises
    ------
        SmiError: the key is truncated.
    """
    arcs: list[str] = []
    at = 0

    while at < len(key):
        width = key[at]
        at += 1

        if width < 1 or at + width > len(key):
            raise error.SmiError(f"truncated OID key at byte {at}")

        arcs.append(str(int.from_bytes(key[at : at + width], "big")))
        at += width

    if not arcs:
        raise error.SmiError("empty OID key")

    return ".".join(arcs)


def subtree_bound(key: bytes) -> bytes:
    """The exclusive upper bound of the subtree rooted at *key*.

    ``oid_key >= key AND oid_key < subtree_bound(key)`` is every node at or
    below that OID.

    Args:
        key: an encoded OID

    Returns
    -------
        The first key sorting above every descendant.
    """
    out = bytearray(key)

    while out and out[-1] == 0xFF:
        out.pop()

    if not out:
        return bytes(key) + b"\xff"

    out[-1] += 1

    return bytes(out)


def best_by_revision(candidates: "list[tuple[Any, str | None]]") -> Any:
    """The best of several copies of one thing, newest revision first.

    Two corpora offering a module are offering the same specification at two
    revisions, and the newer one is the answer wherever it sits in the search
    path -- so the newest MODULE-IDENTITY revision wins and configured order
    only breaks the tie. This is
    :py:meth:`~pysnmp.smi.builder.MibBuilder._candidates` applied to corpora
    rather than to MIB sources, deliberately: a builder that ranked a module
    found in two MIB sources by revision and the same module found in two
    corpora by position would answer one question two ways. It is also
    pysmi's ``PRECEDENCE_NEWEST_REVISION``, which is where the rule was
    settled.

    Configured order settles it when the revisions cannot: when any candidate
    states none -- every SMIv1 module, and the SMI modules themselves -- or
    when they all state the same one. An undated copy cannot be placed
    against a dated one, so a single undated candidate leaves the whole
    decision to order.

    Args:
        candidates: ``(payload, revision)`` in configured order, the revision
            being the corpus ``module.revision`` column, which pysmi fills
            with the newest revision the module states

    Returns
    -------
        The winning payload, or ``None`` for no candidates.
    """
    if not candidates:
        return None

    revisions = [revision for _, revision in candidates]

    if not all(revisions) or len(set(revisions)) == 1:
        return candidates[0][0]

    # max() returns the first maximal element, so candidates sharing the
    # newest revision keep the order they were configured in.
    return max(candidates, key=lambda pair: pair[1] or "")[0]


def revision_rank(revision: "str | None") -> int:
    """A MODULE-IDENTITY revision as a number that sorts newest first.

    Args:
        revision: the corpus ``module.revision`` column, ``YYYYMMDDHHMM``
            followed by a ``Z``, or ``None``

    Returns
    -------
        The negated stamp, so a later date sorts lower in a rule where lower
        wins, and 0 for a module stating no revision -- which therefore sorts
        after every module that states one. pysmi's ``index.revision_rank``.
    """
    if not revision or not revision[:12].isdigit():
        return 0

    return -int(revision[:12])


def best_by_corpus_rank(candidates: "list[tuple[str, tuple[Any, ...]]]") -> str | None:
    """The module that owns an arc, by the corpus rule, lower rank winning.

    Args:
        candidates: ``(module, rank)``, the rank as
            :py:meth:`~pysnmp.smi.corpus.CompositeMibCorpus.rank_of` builds it

    Returns
    -------
        The winning module name, or ``None`` for no candidates.
    """
    if not candidates:
        return None

    return min(candidates, key=lambda pair: pair[1])[0]


class MibCorpus:
    """A corpus database, opened read-only.

    Args:
        path: the ``core.db`` to open

    Raises
    ------
        SmiError: the file is missing, is not a corpus, or carries a schema
            version this pysnmp cannot read.
    """

    #: The queries, named. Kept together because they are the whole of what
    #: this class is: a corpus is a file format, and a reader of it is these
    #: statements plus the OID codec above.
    QUERIES: Final[dict[str, str]] = {
        "meta": "SELECT value FROM meta WHERE key = ?",
        "find_module": "SELECT module FROM oid_index WHERE oid_key = ?",
        "node_at": (
            "SELECT module, name, oid, class, nodetype, status, maxaccess, "
            "units, syntax, defval, indices, augments FROM node "
            "WHERE oid_key = ? ORDER BY module LIMIT 1"
        ),
        "node_at_in": (
            "SELECT module, name, oid, class, nodetype, status, maxaccess, "
            "units, syntax, defval, indices, augments FROM node "
            "WHERE oid_key = ? AND module = ?"
        ),
        "node_named": (
            "SELECT module, name, oid, class, nodetype, status, maxaccess, "
            "units, syntax, defval, indices, augments FROM node "
            "WHERE module = ? AND name = ?"
        ),
        "nodes_of": (
            "SELECT module, name, oid, class, nodetype, status, maxaccess, "
            "units, syntax, defval, indices, augments FROM node "
            "WHERE module = ? ORDER BY oid_key"
        ),
        "next_node": (
            "SELECT module, name, oid, class, nodetype, status, maxaccess, "
            "units, syntax, defval, indices, augments FROM node "
            "WHERE oid_key > ? ORDER BY oid_key, module LIMIT 1"
        ),
        "subtree": (
            "SELECT module, name, oid, class, nodetype, status, maxaccess, "
            "units, syntax, defval, indices, augments FROM node "
            "WHERE oid_key >= ? AND oid_key < ? ORDER BY oid_key, module"
        ),
        "symbols_of": (
            "SELECT name, class, status, displayhint, type FROM symbol "
            "WHERE module = ? ORDER BY name"
        ),
        "symbol": (
            "SELECT name, class, status, displayhint, type FROM symbol "
            "WHERE module = ? AND name = ?"
        ),
        "imports_of": "SELECT name, source FROM import WHERE module = ?",
        "type": "SELECT spec FROM type WHERE id = ?",
        "module": (
            "SELECT name, tier, oid, lastupdated, revision, content_hash, nodes "
            "FROM module WHERE name = ?"
        ),
        "modules": "SELECT name FROM module ORDER BY name",
    }

    #: The ``node`` columns :py:data:`QUERIES` selects, in order, so a row
    #: becomes a dict without every caller repeating the list.
    NODE_FIELDS: Final[tuple[str, ...]] = (
        "module",
        "name",
        "oid",
        "class",
        "nodetype",
        "status",
        "maxaccess",
        "units",
        "syntax",
        "defval",
        "indices",
        "augments",
    )

    def __init__(self, path: str):
        """Open the corpus at *path*, refusing one this pysnmp cannot read."""
        if not os.path.exists(path):
            raise error.SmiError(f"no MIB corpus at {path}")

        self._path = os.path.abspath(path)

        # immutable=1 says the file cannot change, so SQLite takes no locks and
        # needs nothing writable near it -- which is what lets a corpus be
        # mounted read-only from a container image volume.
        #
        # The path is percent-encoded first because this is a URI, not a path.
        # A directory named "we?ird" otherwise ends the path at the "?" and
        # SQLite opens an empty database of that shorter name -- which does not
        # raise, it simply answers nothing, and the corpus reads as a file with
        # application_id 0.
        #
        # os.path.exists above says something is there, not that SQLite can
        # open it: a directory, or a file this process may not read, gets past
        # it and fails here. Every other rejection below is an SmiError, and a
        # caller that catches one to fall back to its MIB sources should not
        # have a bare sqlite3 error come through this one path instead.
        uri = f"file:{urllib.request.pathname2url(self._path)}?immutable=1"

        try:
            self._db = sqlite3.connect(uri, uri=True)

        except sqlite3.Error as exc:
            raise error.SmiError(f"cannot open MIB corpus {path}: {exc}") from exc

        try:
            application = self._db.execute("PRAGMA application_id").fetchone()[0]
            version = self._db.execute("PRAGMA user_version").fetchone()[0]

        except sqlite3.DatabaseError as exc:
            self._db.close()
            raise error.SmiError(f"{path} is not a MIB corpus: {exc}") from exc

        if application != APPLICATION_ID:
            self._db.close()
            raise error.SmiError(
                f"{path} is not a MIB corpus: application_id {application:#x}"
            )

        if version != SCHEMA_VERSION:
            self._db.close()
            raise error.SmiError(
                f"MIB corpus {path} is schema version {version}; this pysnmp "
                f"reads version {SCHEMA_VERSION}"
            )

        # A negative result is cached too: a dangling type id is a corpus
        # defect, and re-querying for it on every node that carries it turns
        # one defect into a per-row cost.
        self._types: dict[int, dict[str, Any] | None] = {}
        self._modules: frozenset[str] | None = None

    def __repr__(self) -> str:
        """The corpus and where it came from."""
        return f"{self.__class__.__name__}({self._path!r})"

    @property
    def path(self) -> str:
        """Where this corpus was opened from."""
        return self._path

    def close(self) -> None:
        """Release the database."""
        self._db.close()

    def meta(self, key: str) -> str | None:
        """One value from the corpus metadata.

        Args:
            key: ``schema_version``, ``corpus_version``, ``corpus_id``,
                ``texts``, or one of the counts

        Returns
        -------
            The value as a string, or ``None`` when the corpus carries none.
        """
        row = self._db.execute(self.QUERIES["meta"], (key,)).fetchone()

        return row[0] if row else None

    @property
    def loadTexts(self) -> bool:
        """Whether this corpus carries DESCRIPTION and REFERENCE.

        Always false today: prose is roughly a third of a module's bytes, the
        runtime discards it under the default, and the published ``json/``
        tree already serves the consumer that wants it. The property exists so
        a caller asking for texts can be told rather than quietly handed
        nothing.
        """
        return self.meta("texts") == "1"

    def modules(self) -> frozenset[str]:
        """Every module this corpus carries."""
        if self._modules is None:
            self._modules = frozenset(
                x[0] for x in self._db.execute(self.QUERIES["modules"])
            )

        return self._modules

    def module(self, name: str) -> dict[str, Any] | None:
        """What the corpus records about a module.

        Args:
            name: the module's descriptor

        Returns
        -------
            Its tier, MODULE-IDENTITY OID, revision, content hash and node
            count, or ``None`` when the corpus does not carry it.
        """
        row = self._db.execute(self.QUERIES["module"], (name,)).fetchone()

        if row is None:
            return None

        return dict(
            zip(
                ("name", "tier", "oid", "lastupdated", "revision", "hash", "nodes"),
                row,
            )
        )

    def type_spec(self, identifier: int | None) -> dict[str, Any] | None:
        """A type specification, by the id a node or symbol row carries.

        Cached: a corpus repeats a handful of specifications tens of thousands
        of times, and the id is what makes "the same type" answerable at all.

        Args:
            identifier: ``type.id``, or ``None``

        Returns
        -------
            The specification, or ``None``.
        """
        if identifier is None:
            return None

        if identifier not in self._types:
            row = self._db.execute(self.QUERIES["type"], (identifier,)).fetchone()
            self._types[identifier] = json.loads(row[0]) if row else None

        return self._types[identifier]

    def _node(self, row: tuple[Any, ...] | None) -> dict[str, Any] | None:
        """A ``node`` row as a dict, with its JSON columns decoded."""
        if row is None:
            return None

        node = dict(zip(self.NODE_FIELDS, row))

        for field in ("defval", "indices", "augments"):
            node[field] = json.loads(node[field]) if node[field] else None

        node["syntax"] = self.type_spec(node["syntax"])
        node["arcs"] = tuple(int(x) for x in node["oid"].split("."))

        return node

    def anchor(self, oid: Union[str, "tuple[int, ...]"]) -> str | None:
        """Which module registers *exactly* this OID, without chopping arcs.

        The single index lookup :py:meth:`find_module` repeats as it shortens
        the OID. It is public because a search across several corpora cannot
        be built out of :py:meth:`find_module`: that returns a module name and
        not the length it matched at, so a shallow anchor in one corpus is
        indistinguishable from a deep one in another, and the longest-prefix
        rule the composite owes cannot be applied to the answers. Chopping is
        hoisted into the caller instead, and this is what it calls.

        Args:
            oid: the OID, matched as given

        Returns
        -------
            The module name, or ``None`` when no module anchors this exact
            OID -- which for anything below an anchor is the normal answer.
        """
        row = self._db.execute(self.QUERIES["find_module"], (oid_key(oid),)).fetchone()

        return row[0] if row else None

    def find_module(self, oid: Union[str, "tuple[int, ...]"]) -> str | None:
        """Which module answers for an OID.

        The index carries a module's *anchors* -- what it registers arcs with
        -- so this is a longest-prefix search rather than one lookup: chop an
        arc at a time until one resolves. An instance OID from a trap is a
        column OID plus index arcs and appears in no MIB at all, so chopping
        is the normal case, not the exception.

        Args:
            oid: the OID to resolve

        Returns
        -------
            The module name, or ``None`` when nothing claims a prefix of it.
            A miss is not an error: an unresolved OID still decodes
            structurally as far as the longest known prefix reaches.
        """
        arcs = [int(x) for x in oid.split(".")] if isinstance(oid, str) else list(oid)

        while arcs:
            found = self.anchor(tuple(arcs))

            if found is not None:
                return found

            arcs.pop()

        return None

    def node(
        self, oid: Union[str, "tuple[int, ...]"], module: str | None = None
    ) -> dict[str, Any] | None:
        """The node at an exact OID.

        Args:
            oid: the OID, which must be the node's own and not an instance
            module: which module's definition to take, where more than one
                defines the OID. The first by name otherwise.

        Returns
        -------
            The node, or ``None``.
        """
        key = oid_key(oid)

        if module is None:
            return self._node(
                self._db.execute(self.QUERIES["node_at"], (key,)).fetchone()
            )

        return self._node(
            self._db.execute(self.QUERIES["node_at_in"], (key, module)).fetchone()
        )

    def node_named(self, module: str, name: str) -> dict[str, Any] | None:
        """The node a module declares under a descriptor.

        This is the ``importSymbols(module, name)`` lookup, which is how a
        manager usually arrives rather than by OID.

        Args:
            module: the module's descriptor
            name: the symbol's descriptor

        Returns
        -------
            The node, or ``None``.
        """
        return self._node(
            self._db.execute(self.QUERIES["node_named"], (module, name)).fetchone()
        )

    def next_node(self, oid: Union[str, "tuple[int, ...]"]) -> dict[str, Any] | None:
        """The first node ordered after an OID -- GETNEXT, over the corpus.

        Args:
            oid: where to start, exclusive

        Returns
        -------
            The next node, or ``None`` at the end of the corpus, which is
            ``endOfMibView`` and not an error.
        """
        return self._node(
            self._db.execute(self.QUERIES["next_node"], (oid_key(oid),)).fetchone()
        )

    def subtree(self, oid: Union[str, "tuple[int, ...]"]) -> list[dict[str, Any]]:
        """Every node at or below an OID, in OID order.

        Args:
            oid: the subtree root

        Returns
        -------
            The nodes, root first.
        """
        low = oid_key(oid)

        return [
            self._node(row)  # type: ignore[misc]
            for row in self._db.execute(
                self.QUERIES["subtree"], (low, subtree_bound(low))
            )
        ]

    def nodes_of(self, module: str) -> list[dict[str, Any]]:
        """Every node a module declares, in OID order.

        Args:
            module: the module's descriptor

        Returns
        -------
            The nodes.
        """
        return [
            self._node(row)  # type: ignore[misc]
            for row in self._db.execute(self.QUERIES["nodes_of"], (module,))
        ]

    def symbols_of(self, module: str) -> list[dict[str, Any]]:
        """Every type a module declares, in name order.

        That is its TEXTUAL-CONVENTIONs and its type assignments.

        Args:
            module: the module's descriptor

        Returns
        -------
            The symbols, each with its specification decoded.
        """
        return [
            {
                "name": row[0],
                "class": row[1],
                "status": row[2],
                "displayhint": row[3],
                "type": self.type_spec(row[4]),
            }
            for row in self._db.execute(self.QUERIES["symbols_of"], (module,))
        ]

    def symbol(self, module: str, name: str) -> dict[str, Any] | None:
        """One declared type, by module and descriptor.

        Args:
            module: the module's descriptor
            name: the type's descriptor

        Returns
        -------
            The symbol, or ``None``.
        """
        row = self._db.execute(self.QUERIES["symbol"], (module, name)).fetchone()

        if row is None:
            return None

        return {
            "name": row[0],
            "class": row[1],
            "status": row[2],
            "displayhint": row[3],
            "type": self.type_spec(row[4]),
        }

    def imports_of(self, module: str) -> dict[str, str]:
        """A module's IMPORTS, as symbol to the module defining it.

        Args:
            module: the module's descriptor

        Returns
        -------
            Symbol name to source module.
        """
        return dict(self._db.execute(self.QUERIES["imports_of"], (module,)))


class CompositeMibCorpus:
    """Several corpora searched as one, ranked by the corpus rule.

    A deployment rarely has a single corpus. It has the distribution's, which
    covers the standard modules and whatever vendors were published with it,
    and it has its own -- the enterprise MIBs its devices actually speak, which
    nobody else ships. Both have to be readable at once, and which one answers
    has to be decided by a rule rather than by whichever was configured last.

    **Two different questions, two rules.** Two corpora carrying *the same
    module* carry one specification at two revisions, so the newest wins and
    configured order only breaks the tie -- :py:func:`best_by_revision`, which
    is what :py:meth:`~pysnmp.smi.builder.MibBuilder._candidates` does with two
    MIB sources and what pysmi's ``PRECEDENCE_NEWEST_REVISION`` does with two
    copies of one file. That is :py:meth:`owner`.

    Two corpora anchoring one arc with *different modules* is not that
    question. There is no shared specification and no symmetry to appeal to: a
    wholly obsolete module is not an earlier draft of a live one, and a vendor
    tree bundling its own copy of a standard MIB is not a later revision of it.
    So the arc goes to pysmi's ``rank_index`` rule as far as a corpus carries
    it -- ``(obsolete, tier, revision, name)``, :py:meth:`rank_of` -- which is
    the same rule that decides the arc *inside* a corpus at build time. That is
    :py:meth:`anchor`, and pysnmp/pysnmp#234 is where the two terms a corpus
    cannot carry are recorded.

    **Both paths reach the same copy.** Resolving a name and resolving an OID
    are one question asked twice, so an OID is resolved to a module *name* and
    that name then goes through the same rule. A corpus can therefore anchor
    an OID without owning the module it names: the anchor says which module
    answers, :py:meth:`owner` says whose copy of it is read.

    **By OID the longest prefix still wins first.** First-match-wins on OIDs
    is the bug this class exists to avoid: a private subtree under
    ``enterprises.9`` resolves to the core corpus's anchor for
    ``enterprises.9`` and never reaches the customer corpus that anchors the
    subtree itself, no matter how the two are ordered. Every corpus is asked
    at each prefix length before the OID is shortened; ranking settles only
    what a shorter prefix cannot, which is two corpora naming different
    modules at the *same* length.

    **One module resolves from exactly one corpus.** Where two carry the same
    module, every name-keyed lookup for it routes to the same one, and the
    other's rows for it are not visible -- not its nodes, not its types, not
    its IMPORTS. Merging two corpora for one module would build one module out
    of two definitions and produce distinct class objects for the same type,
    which breaks ``isinstance`` at a distance and is not worth any amount of
    convenience.

    Args:
        *corpora: the corpora, in search order

    Raises
    ------
        SmiError: no corpora were given. There is nothing for an empty
            composite to answer and its every lookup would be ``None``, which
            reads as "the corpora do not carry it" rather than as the
            configuration mistake it is.
    """

    def __init__(self, *corpora: MibCorpus):
        """Take the corpora in search order and index nothing yet."""
        if not corpora:
            raise error.SmiError("a composite MIB corpus needs at least one corpus")

        self._corpora: tuple[MibCorpus, ...] = tuple(corpora)
        self._modules: frozenset[str] | None = None
        self._owners: dict[str, MibCorpus | None] = {}

        # Ranks are read once per module: the obsolete term costs a scan of
        # every node the module declares, and a contested arc asks for the
        # same handful of modules over and over.
        self._ranks: dict[str, tuple[Any, ...]] = {}

    def __repr__(self) -> str:
        """The composite and what it was built from, in order."""
        return f"{self.__class__.__name__}({', '.join(repr(x) for x in self._corpora)})"

    @property
    def corpora(self) -> "tuple[MibCorpus, ...]":
        """The corpora this searches, in the order they were given."""
        return self._corpora

    @property
    def path(self) -> str:
        """Where the corpora were opened from, joined as a search path."""
        return os.pathsep.join(x.path for x in self._corpora)

    def close(self) -> None:
        """Release every corpus."""
        for corpus in self._corpora:
            corpus.close()

    @property
    def loadTexts(self) -> bool:
        """Whether *every* corpus carries DESCRIPTION and REFERENCE.

        All rather than any, because a caller asking for texts is asking about
        the modules they will load, and which corpus answers for a given
        module is not something they chose. One textless corpus in the search
        path means some modules come back with no prose, and reporting texts
        as available would make that indistinguishable from a MIB that
        declares none -- the precise confusion
        :py:meth:`~pysnmp.smi.builder.MibBuilder.setMibCorpus` refuses to
        allow.
        """
        return all(x.loadTexts for x in self._corpora)

    def meta(self, key: str) -> str | None:
        """One metadata value, from the first corpus that carries it.

        Args:
            key: the metadata key

        Returns
        -------
            The value, or ``None`` when no corpus records that key. Note that
            values such as ``corpus_id`` and the counts describe *one* corpus
            and not the search path, so this answers "what does the first
            corpus that has an opinion say", which is useful for diagnostics
            and not much else.
        """
        for corpus in self._corpora:
            value = corpus.meta(key)

            if value is not None:
                return value

        return None

    def modules(self) -> frozenset[str]:
        """Every module any corpus carries."""
        if self._modules is None:
            self._modules = frozenset().union(*(x.modules() for x in self._corpora))

        return self._modules

    def owner(self, module: str) -> MibCorpus | None:
        """Which corpus answers for a module, and will answer for all of it.

        This is the one-module-one-corpus rule made callable: every name-keyed
        lookup here goes through it, so a module's nodes, types and IMPORTS
        cannot come from different corpora. Which corpus that is follows
        :py:func:`best_by_revision` -- newest revision, configured order only
        breaking the tie.

        Args:
            module: the module's descriptor

        Returns
        -------
            The corpus whose copy is read, or ``None`` when none carries it.
        """
        if module not in self._owners:
            candidates = [
                (corpus, (corpus.module(module) or {}).get("revision"))
                for corpus in self._corpora
                if module in corpus.modules()
            ]

            self._owners[module] = best_by_revision(candidates)

        return self._owners[module]

    def module(self, name: str) -> dict[str, Any] | None:
        """What the owning corpus records about a module.

        Args:
            name: the module's descriptor

        Returns
        -------
            Its record, or ``None`` when no corpus carries it.
        """
        owner = self.owner(name)

        return owner.module(name) if owner else None

    def rank_of(self, module: str) -> "tuple[Any, ...]":
        """How a module ranks for an arc it registers, lower winning.

        ``(obsolete, tier, revision, name)``: pysmi's ``index.module_rank``
        less the two terms a corpus cannot supply.

        A module whose every object is obsolete describes an arc nothing
        should decode against, and republishing it later does not change that,
        so obsolete ranks below live whatever the dates say. Tier then settles
        the ordinary case this rule exists for: a vendor tree bundling its own
        copy of a standard MIB does not take the arc from the standard
        definition by having been republished more recently.

        Two of pysmi's terms are missing and cannot be recovered here. How
        strongly a module claims an arc -- MODULE-IDENTITY over
        OBJECT-IDENTITY over neither -- is settled at build time and not
        carried into ``oid_index``. The publishing RFC number is not a corpus
        column at all. Both are noted in pysnmp/pysnmp#234; a contest that
        turns on either falls through to the module name, which is arbitrary
        but total.

        Args:
            module: the module's descriptor

        Returns
        -------
            Its rank, comparable against any other module's.
        """
        if module not in self._ranks:
            record = self.module(module) or {}
            owner = self.owner(module)

            statuses = [
                node["status"]
                for node in (owner.nodes_of(module) if owner else [])
                if node["class"] in OBJECT_CLASSES
            ]

            obsolete = 1 if statuses and all(x == "obsolete" for x in statuses) else 0

            tier = record.get("tier")
            rank = TIERS.index(tier) if tier in TIERS else len(TIERS)

            self._ranks[module] = (
                obsolete,
                rank,
                revision_rank(record.get("revision")),
                module,
            )

        return self._ranks[module]

    def anchor(self, oid: Union[str, "tuple[int, ...]"]) -> str | None:
        """Which module registers exactly this OID, across all corpora.

        Corpora usually agree, naming one module between them. Where they name
        *different* modules for one arc, the contest is the one pysmi's
        ``rank_index`` settles inside a single corpus, so it is settled the
        same way here: by :py:meth:`rank_of`, not by revision alone and not by
        which corpus was configured first.

        This is a different question from :py:meth:`owner`, which is asked of
        two *copies of one module* and stays on
        :py:func:`best_by_revision`. Two copies of one specification differ by
        revision and nothing else, and configured order is a reasonable
        fallback where the revisions cannot separate them. Two different
        modules claiming one arc have no such symmetry: a wholly obsolete
        module and a vendor module are not later drafts of the standard one,
        and an undated module loses outright here rather than sending the
        decision to order.

        Args:
            oid: the OID, matched as given

        Returns
        -------
            The module name, or ``None``.
        """
        seen: set[str] = set()

        for corpus in self._corpora:
            found = corpus.anchor(oid)

            if found is not None:
                seen.add(found)

        return best_by_corpus_rank([(x, self.rank_of(x)) for x in seen])

    def find_module(self, oid: Union[str, "tuple[int, ...]"]) -> str | None:
        """Which module answers for an OID, by longest prefix across all corpora.

        Every corpus is asked at each prefix length before the OID is
        shortened, so a corpus late in the order still wins with a deeper
        anchor than an earlier one. Only anchors of equal length are ranked
        against each other, by :py:meth:`anchor`.

        Args:
            oid: the OID to resolve

        Returns
        -------
            The module name, or ``None`` when no corpus claims a prefix.
        """
        arcs = [int(x) for x in oid.split(".")] if isinstance(oid, str) else list(oid)

        while arcs:
            found = self.anchor(tuple(arcs))

            if found is not None:
                return found

            arcs.pop()

        return None

    def _owned(self, corpus: MibCorpus, node: dict[str, Any] | None) -> bool:
        """Whether a node this corpus returned is one it answers for.

        A node belongs to a module, and a module belongs to one corpus. A
        corpus late in the order still has rows for a module an earlier one
        owns, and those rows are not part of what the composite resolves.

        Args:
            corpus: the corpus the node came from
            node: the node, or ``None``

        Returns
        -------
            Whether it should be visible.
        """
        return node is not None and self.owner(node["module"]) is corpus

    def node(
        self, oid: Union[str, "tuple[int, ...]"], module: str | None = None
    ) -> dict[str, Any] | None:
        """The node at an exact OID, from the corpus that owns its module.

        Args:
            oid: the OID, which must be the node's own and not an instance
            module: which module's definition to take. The first corpus with
                a node at this OID that it owns, otherwise.

        Returns
        -------
            The node, or ``None``.
        """
        if module is not None:
            owner = self.owner(module)

            return owner.node(oid, module) if owner else None

        for corpus in self._corpora:
            found = corpus.node(oid)

            if self._owned(corpus, found):
                return found

        return None

    def node_named(self, module: str, name: str) -> dict[str, Any] | None:
        """The node a module declares under a descriptor.

        Args:
            module: the module's descriptor
            name: the symbol's descriptor

        Returns
        -------
            The node, or ``None``.
        """
        owner = self.owner(module)

        return owner.node_named(module, name) if owner else None

    def next_node(self, oid: Union[str, "tuple[int, ...]"]) -> dict[str, Any] | None:
        """The first node ordered after an OID, across every corpus.

        A walk has to see one ordering, so each corpus is advanced to its own
        first owned successor and the earliest of those wins. Rows for a
        module some other corpus owns are stepped over rather than returned,
        which is what keeps a walk from visiting a module twice under two
        definitions.

        Args:
            oid: where to start, exclusive

        Returns
        -------
            The next node, or ``None`` at the end of every corpus, which is
            ``endOfMibView`` and not an error.
        """
        best: dict[str, Any] | None = None
        bound: bytes | None = None

        for corpus in self._corpora:
            found = corpus.next_node(oid)

            while found is not None and not self._owned(corpus, found):
                found = corpus.next_node(found["arcs"])

            if found is None:
                continue

            key = oid_key(found["arcs"])

            if bound is None or key < bound:
                best, bound = found, key

        return best

    def subtree(self, oid: Union[str, "tuple[int, ...]"]) -> list[dict[str, Any]]:
        """Every owned node at or below an OID, in OID order.

        Args:
            oid: the subtree root

        Returns
        -------
            The nodes, root first, merged across corpora.
        """
        found = [
            node
            for corpus in self._corpora
            for node in corpus.subtree(oid)
            if self._owned(corpus, node)
        ]

        return sorted(found, key=lambda x: (oid_key(x["arcs"]), x["module"]))

    def nodes_of(self, module: str) -> list[dict[str, Any]]:
        """Every node a module declares, from the corpus that owns it.

        Args:
            module: the module's descriptor

        Returns
        -------
            The nodes, or an empty list when no corpus carries the module.
        """
        owner = self.owner(module)

        return owner.nodes_of(module) if owner else []

    def symbols_of(self, module: str) -> list[dict[str, Any]]:
        """Every type a module declares, from the corpus that owns it.

        Args:
            module: the module's descriptor

        Returns
        -------
            The symbols, or an empty list when no corpus carries the module.
        """
        owner = self.owner(module)

        return owner.symbols_of(module) if owner else []

    def symbol(self, module: str, name: str) -> dict[str, Any] | None:
        """One declared type, from the corpus that owns its module.

        Args:
            module: the module's descriptor
            name: the type's descriptor

        Returns
        -------
            The symbol, or ``None``.
        """
        owner = self.owner(module)

        return owner.symbol(module, name) if owner else None

    def imports_of(self, module: str) -> dict[str, str]:
        """A module's IMPORTS, from the corpus that owns it.

        Args:
            module: the module's descriptor

        Returns
        -------
            Symbol name to source module, empty when no corpus carries it.
        """
        owner = self.owner(module)

        return owner.imports_of(module) if owner else {}


def open_corpora(paths: "list[str] | tuple[str, ...]") -> Any:
    """Open a search path of corpora.

    Args:
        paths: the ``.db`` files, in search order

    Returns
    -------
        A :py:class:`MibCorpus` for a single path and a
        :py:class:`CompositeMibCorpus` for several. One path is not wrapped
        because a composite of one answers identically and only obscures the
        corpus in tracebacks and in ``repr``.

    Raises
    ------
        SmiError: no paths were given, or one of them is not a readable
            corpus. A configured corpus that cannot be opened is a mistake to
            report rather than a source to skip: skipping it leaves a
            deployment resolving fewer modules than it asked for, and the only
            symptom is a MIB that used to be found and now is not.
    """
    opened: list[MibCorpus] = []

    try:
        for path in paths:
            opened.append(MibCorpus(path))

    except Exception:
        for corpus in opened:
            corpus.close()

        raise

    if not opened:
        raise error.SmiError("no MIB corpus paths given")

    return opened[0] if len(opened) == 1 else CompositeMibCorpus(*opened)
