"""What changes when the base layer stops being a 2017 freeze.

``pysnmp/smi/mibs/`` holds modules pysmi generated in April 2017 and nobody has
regenerated since. pysmi ships current ones in every wheel we already depend on,
which ``MibBuilder`` ignores. pysnmp/pysnmp#198 is about consuming those instead.

A blind swap is not safe, so this lands first: it loads each module both ways --
the frozen copy, and the generated copy with ``pysmi.mibs.pysnmp`` registered
ahead of our own sources -- and compares what the issue asks for: the exported
symbol set, and per symbol the OID, syntax, constraints, MAX-ACCESS, STATUS,
UNITS, INDEX/AUGMENTS wiring and OBJECTS list.

Every difference the sweep finds today is pinned below, classified, and checked
against the MIB that declares it. The point is not that the two agree -- they do
not -- but that we know exactly where, and that an *unclassified* difference
fails. When the repoint happens, this is what says nothing else moved.

Two normalizations, because they are spelling rather than substance:

* MAX-ACCESS lost its hyphens between generators (``not-accessible`` /
  ``notaccessible``)
* constraints are compared as the effective set of leaves, not the nesting the
  generator chose (``ConstraintsUnion(SingleValueConstraint(...))`` and a bare
  ``SingleValueConstraint(...)`` say the same thing)

See pysnmp/pysnmp#198.
"""

import importlib.util
import json
import pathlib
import warnings

import pytest
from pysmi.codegen import JsonCodeGen
from pysmi.compiler import MibCompiler
from pysmi.parser import SmiV1CompatParser
from pysmi.reader import PackageReader
from pysmi.writer import CallbackWriter

from pysnmp.smi import builder

#: Modules the frozen tree and pysmi's bundle both carry, minus the ones
#: pysnmp/pysnmp#198 keeps hand-written because they carry real behaviour
#: (INET-ADDRESS-MIB, SNMP-FRAMEWORK-MIB, SNMP-TARGET-MIB, SNMPv2-TM,
#: TRANSPORT-ADDRESS-MIB). These eleven are the convergence candidates.
CONVERGENCE_SET = (
    "RFC1158-MIB",
    "RFC1213-MIB",
    "SNMP-COMMUNITY-MIB",
    "SNMP-MPD-MIB",
    "SNMP-NOTIFICATION-MIB",
    "SNMP-PROXY-MIB",
    "SNMP-USER-BASED-SM-MIB",
    "SNMP-USM-AES-MIB",
    "SNMP-USM-HMAC-SHA2-MIB",
    "SNMP-VIEW-BASED-ACM-MIB",
    "SNMPv2-MIB",
)

#: Symbols the frozen copy exports that the generated one does not. Each is an
#: artifact of the 2017 run rather than something a MIB declares. That is not
#: taken on trust: ``test_no_dropped_symbol_is_declared_by_its_mib`` parses each
#: MIB and asserts the symbol is absent from the declared model.
#:
#: ``vacmContextStatus``   RFC 3415's vacmContextTable has one column,
#:                         vacmContextName. There is no such object.
#: ``TtcpInSegs``          A stray leading capital. The frozen module exports it
#:                         bound to tcpInSegs; no ASN.1 anywhere declares the
#:                         name. The generated copy exports tcpInSegs.
#: ``snmpInBadTypes``      Declared in no bundled ASN.1. The bundled RFC1158-MIB
#: ``snmpOutReadOnlys``    is an SMIv1 anchor stub carrying DisplayString and
#:                         the SMI roots, not the whole of RFC 1158.
DROPPED = {
    "SNMP-VIEW-BASED-ACM-MIB": {"vacmContextStatus"},
    "RFC1213-MIB": {"TtcpInSegs"},
    "RFC1158-MIB": {"snmpInBadTypes", "snmpOutReadOnlys"},
}

#: MAX-ACCESS corrections. Every one is an INDEX column that the 2017 run
#: emitted as read-only and the MIB declares not-accessible -- asserted below
#: rather than asserted here, so a future entry cannot be waved through.
#:
#: This is the behaviour change users can observe: an index column stops being
#: readable. RFC 2578 section 7.3 is why -- an index column's value is carried
#: in the OID suffix of every row, so it is recoverable without reading it.
ACCESS_CORRECTIONS = {
    ("SNMP-COMMUNITY-MIB", "snmpCommunityIndex"),
    ("SNMP-NOTIFICATION-MIB", "snmpNotifyFilterSubtree"),
    ("SNMP-NOTIFICATION-MIB", "snmpNotifyName"),
    ("SNMP-PROXY-MIB", "snmpProxyName"),
    ("SNMP-USER-BASED-SM-MIB", "usmUserEngineID"),
    ("SNMP-USER-BASED-SM-MIB", "usmUserName"),
    ("SNMP-VIEW-BASED-ACM-MIB", "vacmAccessContextPrefix"),
    ("SNMP-VIEW-BASED-ACM-MIB", "vacmAccessSecurityLevel"),
    ("SNMP-VIEW-BASED-ACM-MIB", "vacmAccessSecurityModel"),
    ("SNMP-VIEW-BASED-ACM-MIB", "vacmSecurityModel"),
    ("SNMP-VIEW-BASED-ACM-MIB", "vacmSecurityName"),
    ("SNMP-VIEW-BASED-ACM-MIB", "vacmViewTreeFamilySubtree"),
    ("SNMP-VIEW-BASED-ACM-MIB", "vacmViewTreeFamilyViewName"),
    ("SNMPv2-MIB", "sysORIndex"),
}

#: STATUS corrections, both from RFC 3418, which the 2017 copy predates in
#: effect: snmpBasicCompliance is DEPRECATED there (snmpBasicComplianceRev2
#: supersedes it) and snmpObsoleteGroup is OBSOLETE.
STATUS_CORRECTIONS = {
    ("SNMPv2-MIB", "snmpBasicCompliance"): ("current", "deprecated"),
    ("SNMPv2-MIB", "snmpObsoleteGroup"): ("current", "obsolete"),
}

#: The one syntax change in the convergence set. RFC 1213 declares
#: ``atNetAddress SYNTAX NetworkAddress``; RFC 1155 defines NetworkAddress as
#: ``CHOICE { internet IpAddress }`` -- a choice with exactly one arm. The
#: current generator resolves it to that arm. Same values either way, and the
#: constraint set widens from the choice-tag to IpAddress's own sizes.
SYNTAX_CHANGES = {
    ("RFC1213-MIB", "atNetAddress"): ("NetworkAddress", "IpAddress"),
}

GENERATED = pathlib.Path(
    importlib.util.find_spec("pysmi.mibs.pysnmp").submodule_search_locations[0]
)


def _declared(name):
    """Symbol names the MIB actually declares, from parsed ASN.1.

    pysmi is the parser we already depend on, so a question about what a MIB
    declares is answerable exactly rather than approximately.
    """
    documents = {}
    compiler = MibCompiler(
        SmiV1CompatParser(),
        JsonCodeGen(),
        CallbackWriter(
            lambda mibname, data, cbCtx: documents.__setitem__(
                mibname, json.loads(data)
            )
        ),
        useBundledMibs=False,
    )
    compiler.add_sources(PackageReader("pysmi.mibs.asn1"))
    compiler.compile(name, noDeps=True, rebuild=True)

    return {key for key in documents.get(name, {}) if key not in ("meta", "imports")}


def _load(name, generated):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        mibBuilder = builder.MibBuilder()
        if generated:
            mibBuilder.setMibSources(
                builder.DirMibSource(str(GENERATED)), *mibBuilder.getMibSources()
            )
        mibBuilder.loadModules(name)

        return mibBuilder.mibSymbols[name]


def _leaves(constraint):
    """Effective constraints, ignoring how the generator nested them."""
    nested = []
    for sub in getattr(constraint, "_values", ()) or ():
        nested.extend(_leaves(sub))

    return nested or [str(constraint)]


def _ask(getter):
    """Call an accessor, treating "cannot answer" as "not set"."""
    try:
        return getter()
    except Exception:  # noqa: BLE001 -- absent is absent, however it says so
        return None


def _facts(node):
    """Everything pysnmp/pysnmp#198 asks the harness to compare."""
    facts = {"class": type(node).__name__}

    for attr, key in (
        ("getName", "oid"),
        ("getMaxAccess", "maxaccess"),
        ("getStatus", "status"),
        ("getUnits", "units"),
        ("getIndexNames", "indices"),
        ("getAugmentation", "augments"),
        ("getObjects", "objects"),
    ):
        getter = getattr(node, attr, None)
        if not callable(getter):
            continue
        # A node that has the accessor but cannot answer is telling us the same
        # thing as one that returns nothing: the field is not set on it.
        value = _ask(getter)
        if value in (None, "", ()):
            continue
        if key == "maxaccess":
            value = str(value).replace("-", "").lower()
        facts[key] = tuple(value) if isinstance(value, (list, tuple)) else value

    getter = getattr(node, "getSyntax", None)
    if callable(getter):
        syntax = _ask(getter)
        if syntax is not None:
            facts["syntax"] = type(syntax).__name__
            subtype = getattr(syntax, "subtypeSpec", None)
            if subtype is not None:
                seen = set()
                for constraint in subtype:
                    seen.update(_leaves(constraint))
                facts["constraints"] = " | ".join(sorted(seen))

    return facts


@pytest.fixture(scope="module")
def sweep():
    """Every module compared both ways, once."""
    result = {}
    for name in CONVERGENCE_SET:
        frozen, generated = _load(name, False), _load(name, True)
        differences = {}
        for symbol in sorted(set(frozen) & set(generated)):
            before, after = _facts(frozen[symbol]), _facts(generated[symbol])
            changed = {
                key: (before.get(key), after.get(key))
                for key in set(before) | set(after)
                if before.get(key) != after.get(key)
            }
            if changed:
                differences[symbol] = changed
        result[name] = {
            "frozen": frozen,
            "generated": generated,
            "differences": differences,
        }

    return result


class TestSymbolSets:
    """What appears and disappears."""

    def test_only_the_classified_symbols_disappear(self, sweep):
        dropped = {
            name: sorted(set(data["frozen"]) - set(data["generated"]))
            for name, data in sweep.items()
            if set(data["frozen"]) - set(data["generated"])
        }

        assert dropped == {k: sorted(v) for k, v in DROPPED.items()}

    def test_no_dropped_symbol_is_declared_by_its_mib(self):
        """The justification for dropping them, computed from the ASN.1.

        This is the authoritative check, and it parses rather than greps: a
        pattern match over MIB text cannot tell a declaration from a mention in
        a DESCRIPTION, and would call a symbol present because some other
        module's prose names it. ``JsonCodeGen`` gives the declared model, and a
        symbol either is a key in it or is not.
        """
        for module, symbols in sorted(DROPPED.items()):
            declared = set(_declared(module))
            assert declared, f"{module} parsed to nothing"

            for symbol in sorted(symbols):
                assert symbol not in declared, (
                    f"{module} does declare {symbol}; dropping it would lose "
                    f"something the MIB defines"
                )

    def test_the_replacement_for_the_mistyped_symbol_is_declared(self):
        """``TtcpInSegs`` is a stray capital, not a lost object.

        Worth its own assertion: the other three drops lose nothing, but this
        one only holds if the correctly-spelled object is really there.
        """
        declared = _declared("RFC1213-MIB")

        assert "TtcpInSegs" not in declared
        assert "tcpInSegs" in declared

    def test_the_generated_copies_only_add(self, sweep):
        """Convergence is additive except for the classified drops."""
        gained = {
            name: len(set(data["generated"]) - set(data["frozen"]))
            for name, data in sweep.items()
        }

        assert gained["RFC1213-MIB"] > 0, "the 2017 RFC1213-MIB is missing symbols"
        assert gained["RFC1158-MIB"] > 0, "the 2017 RFC1158-MIB is a stripped stub"


class TestFieldDifferences:
    """Every per-symbol difference is one of the classified kinds."""

    def test_no_unclassified_difference_exists(self, sweep):
        unclassified = {}
        for name, data in sweep.items():
            for symbol, changed in data["differences"].items():
                key = (name, symbol)
                for field, (before, after) in changed.items():
                    if field == "maxaccess" and key in ACCESS_CORRECTIONS:
                        continue
                    if field == "status" and STATUS_CORRECTIONS.get(key) == (
                        before,
                        after,
                    ):
                        continue
                    if field == "syntax" and SYNTAX_CHANGES.get(key) == (before, after):
                        continue
                    if field == "constraints" and key in SYNTAX_CHANGES:
                        continue
                    unclassified.setdefault(f"{name}::{symbol}", {})[field] = (
                        before,
                        after,
                    )

        assert unclassified == {}

    def test_every_access_correction_is_an_index_column(self, sweep):
        """The justification for the one user-visible break, asserted.

        An index column is not readable per RFC 2578 section 7.3, and its value
        travels in each row's OID suffix, so nothing becomes unobtainable. If a
        future entry here were *not* an index column, that reasoning would not
        cover it and this fails.
        """
        for name, symbol in sorted(ACCESS_CORRECTIONS):
            generated = sweep[name]["generated"]
            indices = set()
            for node in generated.values():
                getter = getattr(node, "getIndexNames", None)
                if not callable(getter):
                    continue
                for entry in getter() or ():
                    indices.add(entry[2] if len(entry) > 2 else entry)

            assert symbol in indices, f"{name}::{symbol} is not an INDEX column"

    def test_access_corrections_all_move_the_same_way(self, sweep):
        """read-only to not-accessible, never the reverse."""
        for name, symbol in sorted(ACCESS_CORRECTIONS):
            before, after = sweep[name]["differences"][symbol]["maxaccess"]

            assert (before, after) == ("readonly", "notaccessible")


class TestOidsAreStable:
    """The one thing convergence must not change."""

    def test_no_shared_symbol_moves_oid(self, sweep):
        moved = {}
        for name, data in sweep.items():
            for symbol, changed in data["differences"].items():
                if "oid" in changed:
                    moved[f"{name}::{symbol}"] = changed["oid"]

        assert moved == {}
