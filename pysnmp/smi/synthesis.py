#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
# License: https://www.pysnmp.com/pysnmp/license.html
#
"""Building MIB objects from corpus rows instead of executing generated Python.

A pysnmp MIB module is Python that calls back into ``MibBuilder``: it imports
the SMI classes, constructs a ``MibScalar`` or a ``MibTableColumn`` per object,
and exports them. Loading one means running it.

This module produces the same objects from :py:mod:`pysnmp.smi.corpus` rows.
The classes, the constructor arguments and the resulting registrations are the
same ones the generated module would have produced -- what changes is that the
description of them arrived as data rather than as code.

Three consequences, in the order they matter:

**Nothing is executed.** A corpus row is read; no ``exec`` runs, so a corpus
fetched from anywhere cannot be a way to run code in the process that reads it.

**One module at a time, on demand.** The corpus is indexed by OID, so the
module that answers for a trap is found and only that module is built.

**Types keep their identity.** A syntax is stored once in the corpus and
referenced by id, and the class synthesized for it is cached against that id --
so two objects sharing a type share a class, and ``isinstance`` cannot see two
classes for one type (pysnmp/pysnmp#145).

What is not here
----------------

Prose. A corpus carries no DESCRIPTION or REFERENCE, so a builder with
``loadTexts`` set is told rather than quietly handed a module with none: see
:py:func:`load_module`.
"""

from typing import Any

from pysnmp.smi import error
from pysnmp.smi.corpus import MibCorpusCycleError

__all__ = ["load_module", "synthesize_type"]

#: SMI type names as a MIB may spell them, mapped to the pysnmp class that
#: implements each.
#:
#: The jsondoc a corpus is built from records the type name *exactly as the
#: MIB declares it* and never resolves it to an implementation -- that binding
#: is the runtime's, and this table is it. The spellings come from pysmi's own
#: ``typeClasses``, which is the other half of the same contract.
TYPE_CLASSES: dict[str, tuple[str, str]] = {
    "COUNTER32": ("SNMPv2-SMI", "Counter32"),
    "COUNTER64": ("SNMPv2-SMI", "Counter64"),
    "GAUGE32": ("SNMPv2-SMI", "Gauge32"),
    "INTEGER": ("SNMPv2-SMI", "Integer32"),
    "INTEGER32": ("SNMPv2-SMI", "Integer32"),
    "IPADDRESS": ("SNMPv2-SMI", "IpAddress"),
    "NETWORKADDRESS": ("SNMPv2-SMI", "IpAddress"),
    "OBJECT IDENTIFIER": ("ASN1", "ObjectIdentifier"),
    "OCTET STRING": ("ASN1", "OctetString"),
    "OPAQUE": ("SNMPv2-SMI", "Opaque"),
    "TIMETICKS": ("SNMPv2-SMI", "TimeTicks"),
    "UNSIGNED32": ("SNMPv2-SMI", "Unsigned32"),
    "BITS": ("SNMPv2-SMI", "Bits"),
    "COUNTER": ("SNMPv2-SMI", "Counter32"),
    "GAUGE": ("SNMPv2-SMI", "Gauge32"),
}

#: The node classes, by what the corpus records the symbol as.
#:
#: ``objecttype`` is absent because one row is not enough to place it: a
#: ``nodetype`` of table, row or column decides, and :py:func:`_object_class`
#: reads it.
NODE_CLASSES: dict[str, str] = {
    "moduleidentity": "ModuleIdentity",
    "objectidentity": "ObjectIdentity",
    "notificationtype": "NotificationType",
    "objectgroup": "ObjectGroup",
    "notificationgroup": "NotificationGroup",
    "modulecompliance": "ModuleCompliance",
    "agentcapabilities": "AgentCapabilities",
}

#: ``nodetype`` to the class an OBJECT-TYPE becomes.
OBJECT_CLASSES: dict[str, str] = {
    "scalar": "MibScalar",
    "table": "MibTable",
    "row": "MibTableRow",
    "column": "MibTableColumn",
}

#: Where each node class is imported from.
CLASS_SOURCES: dict[str, str] = {
    "ModuleIdentity": "SNMPv2-SMI",
    "ObjectIdentity": "SNMPv2-SMI",
    "NotificationType": "SNMPv2-SMI",
    "MibIdentifier": "SNMPv2-SMI",
    "MibScalar": "SNMPv2-SMI",
    "MibTable": "SNMPv2-SMI",
    "MibTableRow": "SNMPv2-SMI",
    "MibTableColumn": "SNMPv2-SMI",
    "ObjectGroup": "SNMPv2-CONF",
    "NotificationGroup": "SNMPv2-CONF",
    "ModuleCompliance": "SNMPv2-CONF",
    "AgentCapabilities": "SNMPv2-CONF",
}


class _Resolver:
    """Turns corpus type specifications into pysnmp classes, for one module.

    Held for the length of one :py:func:`load_module` because most of what it
    does is answer the same few questions repeatedly -- what is
    ``DisplayString``, what is ``MibTableColumn`` -- and each answer costs an
    ``importSymbols`` that may load another module.
    """

    def __init__(self, builder: Any, corpus: Any, module: str):
        self._builder = builder
        self._corpus = corpus
        self._module = module
        self._imports = corpus.imports_of(module)
        self._local: dict[str, Any] = {}
        self._cache: dict[str, Any] = {}

    def base(self, name: str) -> Any:
        """One of the SMI classes a generated module imports at its top."""
        if name not in self._cache:
            source = CLASS_SOURCES.get(name)

            if source is None:
                raise error.SmiError(f"no source known for SMI class {name}")

            (self._cache[name],) = self._builder.importSymbols(source, name)

        return self._cache[name]

    def refinement(self, name: str) -> Any:
        """One of the constraint classes, from ``ASN1-REFINEMENT``."""
        if name not in self._cache:
            (self._cache[name],) = self._builder.importSymbols("ASN1-REFINEMENT", name)

        return self._cache[name]

    @property
    def builder(self) -> Any:
        """The builder this resolver imports through."""
        return self._builder

    def declare(self, name: str, cls: Any) -> None:
        """Record a type this module declares, so its own objects can use it."""
        self._local[name] = cls

    def declared(self, name: str) -> Any | None:
        """A type this module has already declared, or ``None``."""
        return self._local.get(name)

    def type_class(self, name: str) -> Any:
        """The class implementing an SMI type name.

        Resolution order, and each step is there for a reason:

        1. A type this module declares itself. A module's own
           TEXTUAL-CONVENTION shadows anything of the same name elsewhere.
        2. A base SMI type, through :py:data:`TYPE_CLASSES`.
        3. Whatever the module's IMPORTS says defines it -- which may load
           that module, from disk or from the corpus, and is how a vendor
           module's ``DisplayString`` resolves to the one the precompiled
           ``SNMPv2-TC`` already exported.

        Args:
            name: the type name as the MIB declares it

        Returns:
            The class.

        Raises:
            SmiError: nothing defines the name. Loudly, rather than
                substituting a base type: a column silently typed
                ``OctetString`` instead of its TEXTUAL-CONVENTION renders
                every value wrong and looks like a device fault.
        """
        if name in self._local:
            return self._local[name]

        if name in self._cache:
            return self._cache[name]

        spelling = TYPE_CLASSES.get(name.upper()) or TYPE_CLASSES.get(name)

        if spelling:
            module, symbol = spelling
            (resolved,) = self._builder.importSymbols(module, symbol)

        else:
            resolved = None

            if name in self._imports:
                # Where IMPORTS says it comes from, which is right almost
                # always and wrong in one recurring way: a vendor module
                # written against an older revision of a standard module
                # imports a type that revision defined and the current one
                # does not. BRIDGE-MIB is the case that keeps coming up --
                # RFC 1493 defined MacAddress, RFC 4188 imports it from
                # SNMPv2-TC instead -- and the corpus carries the newer
                # revision because that is what the ranking rule picks.
                resolved = self._try(self._imports[name], name)

            if resolved is None:
                # Not where the MIB said, or not imported at all. Some MIBs
                # simply use a standard type without importing it. Either way
                # the two modules that define almost all of them are worth
                # trying before giving up on the whole module: an unresolved
                # import is a degrade, and refusing to load anything is worse
                # than resolving a type from where it actually lives.
                for module in ("SNMPv2-TC", "SNMPv2-SMI"):
                    resolved = self._try(module, name)

                    if resolved is not None:
                        break

            if resolved is None:
                raise error.SmiError(
                    f"{self._module}: no definition for type {name!r}, which it "
                    f"neither declares nor imports from anything that has it"
                )

        self._cache[name] = resolved

        return resolved

    def imported_from(self, name: str) -> str | None:
        """Which module this one's IMPORTS says defines a symbol."""
        return self._imports.get(name)

    def try_symbol(self, module: str, name: str) -> Any | None:
        """A symbol, or ``None`` when that module does not offer one."""
        return self._try(module, name)

    def _try(self, module: str, name: str) -> Any | None:
        """Import a symbol, or ``None`` if that module has no such thing.

        Args:
            module: where to look
            name: the symbol

        Returns:
            The symbol, or ``None``.
        """
        try:
            (symbol,) = self._builder.importSymbols(module, name)

        except MibCorpusCycleError:
            # A cycle is a structural defect in the corpus, not "that module
            # does not have this symbol". Swallowing it here would report the
            # type as undefined and hide what is actually wrong.
            raise

        except error.SmiError:
            return None

        return symbol

    def constraints(self, spec: dict[str, Any]) -> Any | None:
        """The subtype constraint a specification asks for, or ``None``.

        Args:
            spec: a corpus type specification

        Returns:
            A single constraint, or a union of several.
        """
        declared = spec.get("constraints") or {}
        parts = []

        if "range" in declared:
            rangeConstraint = self.refinement("ValueRangeConstraint")
            parts += [rangeConstraint(x["min"], x["max"]) for x in declared["range"]]

        if "size" in declared:
            sizeConstraint = self.refinement("ValueSizeConstraint")
            parts += [sizeConstraint(x["min"], x["max"]) for x in declared["size"]]

        if "enumeration" in declared:
            singleValue = self.refinement("SingleValueConstraint")
            parts.append(singleValue(*sorted(declared["enumeration"].values())))

        if not parts:
            return None

        if len(parts) == 1:
            return parts[0]

        return self.refinement("ConstraintsUnion")(*parts)

    def enumeration(self, spec: dict[str, Any]) -> Any | None:
        """The ``NamedValues`` a specification asks for, or ``None``."""
        declared = (spec.get("constraints") or {}).get("enumeration")
        bits = spec.get("bits")
        labels = declared or bits

        if not labels:
            return None

        (namedValues,) = self._builder.importSymbols("ASN1-ENUMERATION", "NamedValues")

        return namedValues(*sorted(labels.items(), key=lambda x: x[1]))


def synthesize_type(resolver: "_Resolver", spec: dict[str, Any]) -> Any:
    """An instance of the type a specification describes, constrained.

    Args:
        resolver: the module's resolver
        spec: a corpus type specification

    Returns:
        An instance ready to be handed to a ``MibScalar`` or a column.
    """
    if not spec.get("type"):
        # _textual_convention already refuses this; a node's syntax deserves
        # the same answer rather than a KeyError from three frames down.
        raise error.SmiError(f"type specification carries no type: {spec!r}")

    base = resolver.type_class(spec["type"])
    instance = base()

    values = resolver.enumeration(spec)

    if values is not None:
        instance = instance.clone(namedValues=values)

    constraint = resolver.constraints(spec)

    if constraint is not None:
        instance = instance.subtype(subtypeSpec=constraint)

    return instance


def _textual_convention(resolver: "_Resolver", symbol: dict[str, Any]) -> Any:
    """The class a TEXTUAL-CONVENTION or type assignment becomes.

    Built with :py:func:`type` rather than executed, but otherwise the class a
    generated module declares: the base type and ``TextualConvention`` as
    bases, and the status, display hint and constraints as class attributes.
    """
    spec = symbol.get("type") or {}

    if not spec.get("type"):
        raise error.SmiError(f"{symbol['name']}: type declaration carries no type")

    base = resolver.type_class(spec["type"])
    attributes: dict[str, Any] = {}

    if symbol.get("status"):
        attributes["status"] = symbol["status"]

    if symbol.get("displayhint"):
        attributes["displayHint"] = symbol["displayhint"]

    constraint = resolver.constraints(spec)

    if constraint is not None:
        attributes["subtypeSpec"] = base.subtypeSpec + constraint

    values = resolver.enumeration(spec)

    if values is not None:
        attributes["namedValues"] = values

    if symbol["class"] == "textualconvention":
        (convention,) = resolver.builder.importSymbols("SNMPv2-TC", "TextualConvention")
        bases: tuple[Any, ...] = (base, convention)

    else:
        bases = (base,)

    return type(symbol["name"], bases, attributes)


def _object_class(resolver: "_Resolver", node: dict[str, Any]) -> Any:
    """The class a node row becomes."""
    if node["class"] == "objecttype":
        name = OBJECT_CLASSES.get(node["nodetype"] or "")

        if name is None:
            raise error.SmiError(
                f"{node['module']}::{node['name']}: OBJECT-TYPE with "
                f"unknown nodetype {node['nodetype']!r}"
            )

        return resolver.base(name)

    name = NODE_CLASSES.get(node["class"])

    if name is None:
        # A class the corpus carries and this runtime has no object for. Fall
        # back to a bare registration rather than dropping the arc: the OID is
        # still real and a walk should still see it.
        return resolver.base("MibIdentifier")

    return resolver.base(name)


def _build_node(resolver: "_Resolver", node: dict[str, Any]) -> Any:
    """One MIB object, from one corpus row."""
    cls = _object_class(resolver, node)
    arcs = node["arcs"]

    if node["class"] == "objecttype" and node["nodetype"] in ("scalar", "column"):
        if not node["syntax"]:
            raise error.SmiError(
                f"{node['module']}::{node['name']}: {node['nodetype']} with no syntax"
            )

        obj = cls(arcs, synthesize_type(resolver, node["syntax"]))

    else:
        obj = cls(arcs)

    if node.get("maxaccess") and hasattr(obj, "setMaxAccess"):
        # The runtime compares against the hyphenless spelling, which is what
        # the generated modules carry; the corpus keeps the MIB's own.
        obj = obj.setMaxAccess(node["maxaccess"].replace("-", ""))

    if node.get("units") and hasattr(obj, "setUnits"):
        obj = obj.setUnits(node["units"])

    if node["nodetype"] == "row":
        if node.get("indices"):
            obj = obj.setIndexNames(
                *[
                    (int(x.get("implied", 0)), x["module"], x["object"])
                    for x in node["indices"]
                ]
            )

    return obj


def _wire_augmentations(
    resolver: "_Resolver", modName: str, nodes: list, symbols: dict[str, Any]
) -> None:
    """Give every augmenting row the index names of the row it augments.

    An augmenting row declares AUGMENTS and no INDEX: it is indexed by the row
    it extends. A generated module emits two things for it, and both matter --
    the base row is told it has an augmentation, and this row adopts the base
    row's index names. Without the second, a ``MibTableRow`` cannot turn an
    instance OID into index values or build one, so the table is unreadable and
    unwritable while looking perfectly well-formed. It is not a rare shape:
    1,181 rows in pysnmp/mibs' corpus use AUGMENTS and every one declares no
    INDEX.

    A separate pass because the base row is usually in *this* module --
    ``ifXEntry`` augments ``ifEntry``, both in ``IF-MIB`` -- so it has to be
    resolved from what this build has made rather than through
    ``importSymbols``, which would re-enter the load of a module already being
    built.

    Args:
        resolver: the module's resolver, for a base row in another module
        modName: the module being built
        nodes: its corpus rows
        symbols: what has been built so far, keyed by descriptor
    """
    for node in nodes:
        augments = node.get("augments")

        if node["nodetype"] != "row" or not augments or node.get("indices"):
            continue

        base = symbols.get(augments["object"])

        if base is None:
            # Not this module's own row. The reference names the defining
            # module, but a corpus built from MIBs nobody controls carries
            # references that name the wrong one, so a miss here is resolved
            # the ordinary way rather than trusted.
            base = resolver.try_symbol(augments["module"], augments["object"])

        if base is None:
            # The reference is supposed to name the defining module, and for
            # AUGMENTS it frequently names the importing one instead --
            # CISCO-TCP-MIB::ciscoTcpConnEntry records its base as
            # CISCO-TCP-MIB::tcpConnEntry, though tcpConnEntry is TCP-MIB's.
            # The IMPORTS clause knows where it actually came from.
            source = resolver.imported_from(augments["object"])

            if source:
                base = resolver.try_symbol(source, augments["object"])

        if base is None or not hasattr(base, "getIndexNames"):
            # An augmentation that cannot be resolved costs this row its index
            # names, which is what it had before; refusing the whole module
            # over it would be a worse trade.
            continue

        base.registerAugmentions((modName, node["name"]))
        symbols[node["name"]].setIndexNames(*base.getIndexNames())


def load_module(builder: Any, corpus: Any, modName: str) -> bool:
    """Build a module's symbols from the corpus and export them.

    Args:
        builder: the ``MibBuilder`` to export into
        corpus: an open :py:class:`~pysnmp.smi.corpus.MibCorpus`
        modName: the module to build

    Returns:
        Whether the corpus carried the module. ``False`` leaves the builder
        untouched, so a caller can go on looking elsewhere.

    Raises:
        SmiError: the corpus carries the module but it could not be built --
            an unresolvable type, an OBJECT-TYPE the runtime has no class for.
            Loudly on purpose: a half-built module resolves some OIDs and not
            others, which is worse to diagnose than a module that would not
            load at all.
    """
    if modName not in corpus.modules():
        return False

    resolver = _Resolver(builder, corpus, modName)
    symbols: dict[str, Any] = {}

    # Types first: a module's own objects refer to them, and its TCs may refer
    # to each other. Corpus order is by name, which is not declaration order,
    # so a TC built on another declared later is resolved on demand rather
    # than assumed to be present.
    declared = {x["name"]: x for x in corpus.symbols_of(modName)}
    building: set[str] = set()

    def declare(name: str) -> Any:
        existing = resolver.declared(name)

        if existing is not None:
            return existing

        if name in building:
            raise error.SmiError(
                f"{modName}: type {name!r} is defined in terms of itself"
            )

        building.add(name)

        try:
            spec = declared[name].get("type") or {}
            dependency = spec.get("type")

            if (
                isinstance(dependency, str)
                and dependency != name
                and dependency in declared
            ):
                declare(dependency)

            cls = _textual_convention(resolver, declared[name])

        finally:
            building.discard(name)

        resolver.declare(name, cls)
        symbols[name] = cls

        return cls

    for name in declared:
        declare(name)

    identity = None
    nodes = corpus.nodes_of(modName)

    for node in nodes:
        symbols[node["name"]] = _build_node(resolver, node)

        if node["class"] == "moduleidentity":
            identity = symbols[node["name"]]

    if identity is not None:
        symbols[builder.moduleID] = identity

    builder.exportSymbols(modName, **symbols)

    # After the export, not before: resolving a base row in another module
    # loads that module, and it may import a type back from this one. Wiring
    # first would ask for symbols this build had not published yet.
    _wire_augmentations(resolver, modName, nodes, symbols)

    return True
