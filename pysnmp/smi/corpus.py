#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
# License: https://www.pysnmp.com/pysnmp/license.html
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
from typing import Any, Final, Union

from pysnmp.smi import error

__all__ = ["MibCorpus", "oid_from_key", "oid_key", "subtree_bound"]

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

    Returns:
        The sort key.

    Raises:
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

    Returns:
        The OID, dotted decimal.

    Raises:
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

    Returns:
        The first key sorting above every descendant.
    """
    out = bytearray(key)

    while out and out[-1] == 0xFF:
        out.pop()

    if not out:
        return bytes(key) + b"\xff"

    out[-1] += 1

    return bytes(out)


class MibCorpus:
    """A corpus database, opened read-only.

    Args:
        path: the ``core.db`` to open

    Raises:
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
        if not os.path.exists(path):
            raise error.SmiError(f"no MIB corpus at {path}")

        self._path = os.path.abspath(path)

        # immutable=1 says the file cannot change, so SQLite takes no locks and
        # needs nothing writable near it -- which is what lets a corpus be
        # mounted read-only from a container image volume.
        self._db = sqlite3.connect(f"file:{self._path}?immutable=1", uri=True)

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

        Returns:
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

        Returns:
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

        Returns:
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

    def find_module(self, oid: Union[str, "tuple[int, ...]"]) -> str | None:
        """Which module answers for an OID.

        The index carries a module's *anchors* -- what it registers arcs with
        -- so this is a longest-prefix search rather than one lookup: chop an
        arc at a time until one resolves. An instance OID from a trap is a
        column OID plus index arcs and appears in no MIB at all, so chopping
        is the normal case, not the exception.

        Args:
            oid: the OID to resolve

        Returns:
            The module name, or ``None`` when nothing claims a prefix of it.
            A miss is not an error: an unresolved OID still decodes
            structurally as far as the longest known prefix reaches.
        """
        arcs = [int(x) for x in oid.split(".")] if isinstance(oid, str) else list(oid)

        while arcs:
            row = self._db.execute(
                self.QUERIES["find_module"], (oid_key(tuple(arcs)),)
            ).fetchone()

            if row:
                return row[0]

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

        Returns:
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

        Returns:
            The node, or ``None``.
        """
        return self._node(
            self._db.execute(self.QUERIES["node_named"], (module, name)).fetchone()
        )

    def next_node(self, oid: Union[str, "tuple[int, ...]"]) -> dict[str, Any] | None:
        """The first node ordered after an OID -- GETNEXT, over the corpus.

        Args:
            oid: where to start, exclusive

        Returns:
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

        Returns:
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

        Returns:
            The nodes.
        """
        return [
            self._node(row)  # type: ignore[misc]
            for row in self._db.execute(self.QUERIES["nodes_of"], (module,))
        ]

    def symbols_of(self, module: str) -> list[dict[str, Any]]:
        """Every type a module declares -- its TEXTUAL-CONVENTIONs and type
        assignments -- in name order.

        Args:
            module: the module's descriptor

        Returns:
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

        Returns:
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

        Returns:
            Symbol name to source module.
        """
        return dict(self._db.execute(self.QUERIES["imports_of"], (module,)))
