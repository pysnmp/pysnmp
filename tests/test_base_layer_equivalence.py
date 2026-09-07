"""What changes when the base layer stops being a 2017 freeze.

``pysnmp/smi/mibs/`` holds modules pysmi generated in April 2017 and nobody has
regenerated since. pysmi ships current ones in every wheel we already depend on,
which ``MibBuilder`` ignores. pysnmp/pysnmp#198 is about consuming those instead.

The swap has happened. Best-match selection would have picked pysmi's copies on
revision alone, except that the frozen ones state no revision at all -- pysmi
0.1.3 emitted ``setRevisions`` under ``loadTexts`` and no module-level constant
-- so the tie rule kept handing them the win until they were deleted.

Deleting them removes the evidence of what they said, so it was taken first:
``tests/data/base-layer-2017.json`` holds every symbol of all eleven as the
frozen files defined them, captured at the commit before the deletion. This
compares what loads now against that record -- the exported symbol set, and per
symbol the OID, syntax, constraints, MAX-ACCESS, STATUS, UNITS, INDEX/AUGMENTS
wiring and OBJECTS list.

Every difference is pinned below, classified, and checked against the MIB that
declares it. The point is not that the two agree -- they do not -- but that we
know exactly where, and that an *unclassified* difference fails. It keeps
saying so: a pysmi upgrade that changes one of these modules lands here.

The snapshot is a historical record and nothing can regenerate it, which is the
point -- it is the only remaining account of what the base layer was, and it is
what makes the deletion reviewable rather than a leap.

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
    "SNMPv2-MIB",
)

#: The twelfth module both trees carry, and the one that did not converge.
#:
#: ``pysnmp/smi/mibs/SNMP-VIEW-BASED-ACM-MIB.py`` is not a generated module. It
#: carries a hand-added ``vacmContextStatus`` RowStatus column at
#: ``1.3.6.1.6.3.16.1.1.1.2``, under a comment in the file saying so outright --
#: *"The RowStatus column is not present in the MIB"*. RFC 3415's
#: vacmContextTable has one column, ``vacmContextName``, and is read-only;
#: ``pysnmp.entity.config.addContext`` creates its rows by writing
#: ``createAndGo`` to the fabricated one, addressing it by sub-identifier.
#:
#: That is engine behaviour, so it stays here by the same rule that keeps
#: SNMP-FRAMEWORK-MIB and the rest. It converges once the engine stops needing
#: a column no MIB declares -- pysnmp/pysnmp#205.
HELD_BACK = "SNMP-VIEW-BASED-ACM-MIB"

#: Symbols the frozen copy exports that the generated one does not. Each is an
#: artifact of the 2017 run rather than something a MIB declares. That is not
#: taken on trust: ``test_no_dropped_symbol_is_declared_by_its_mib`` parses each
#: MIB and asserts the symbol is absent from the declared model.
#:
#: ``TtcpInSegs``          A stray leading capital. The frozen module exports it
#:                         bound to tcpInSegs; no ASN.1 anywhere declares the
#:                         name. The generated copy exports tcpInSegs.
#: ``snmpInBadTypes``      Declared in no bundled ASN.1. The bundled RFC1158-MIB
#: ``snmpOutReadOnlys``    is an SMIv1 anchor stub carrying DisplayString and
#:                         the SMI roots, not the whole of RFC 1158.
DROPPED = {
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

#: Facts extracted from ``pysnmp/smi/mibs/`` at the commit before the frozen
#: modules were deleted. See the module docstring.
SNAPSHOT = pathlib.Path(__file__).parent / "data" / "base-layer-2017.json"


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


def _load(name):
    """The module a plain builder resolves, with no source coaxing.

    Nothing is prepended: this asks what a caller actually gets. If the frozen
    copies came back the sweep would compare the snapshot against itself, the
    classified drops would vanish, and ``TestSymbolSets`` would fail.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        mibBuilder = builder.MibBuilder()
        mibBuilder.loadModules(name)

        return mibBuilder.mibSymbols[name]


def _jsonable(value):
    """Tuples and lists compare equal only once both are lists."""
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]

    return value


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
    """Every module measured against the 2017 record, once."""
    frozen_modules = json.loads(SNAPSHOT.read_text())["modules"]

    assert sorted(frozen_modules) == sorted((*CONVERGENCE_SET, HELD_BACK)), (
        "the snapshot and the convergence set have drifted apart"
    )

    result = {}
    for name in CONVERGENCE_SET:
        frozen, generated = frozen_modules[name], _load(name)
        differences = {}
        for symbol in sorted(set(frozen) & set(generated)):
            before = frozen[symbol]
            after = {k: _jsonable(v) for k, v in _facts(generated[symbol]).items()}
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
        """Nothing vanishes that `DROPPED` does not already account for.

        Equality rather than containment, so a symbol that stops disappearing
        fails here too and the record cannot drift ahead of the code.
        """
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
        """Every field that changed is a correction this branch reasoned about.

        The MAX-ACCESS and STATUS corrections are pinned per symbol, so a
        difference in any other field -- or in one of those on a symbol not
        listed -- is unaccounted for and fails.
        """
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
        """A symbol both layers define keeps its OID.

        Access, status and syntax are corrections a caller can absorb. An OID
        that moved would silently redirect every request naming that symbol,
        so there is no acceptable count here other than zero.
        """
        moved = {}
        for name, data in sweep.items():
            for symbol, changed in data["differences"].items():
                if "oid" in changed:
                    moved[f"{name}::{symbol}"] = changed["oid"]

        assert moved == {}


class TestTheFreezeIsGone:
    """The deletion itself, so it cannot be quietly undone."""

    def test_no_converged_module_is_shipped_by_pysnmp(self):
        """Re-freezing one would take the tie and shadow pysmi's copy.

        A generated ``.py`` committed back here states no revision, so best
        match cannot separate it from pysmi's and source order hands it the
        win -- silently, and for good. That is how the base layer stayed on
        2017 in the first place.
        """
        shipped = pathlib.Path(builder.__file__).parent / "mibs"
        refrozen = sorted(
            name for name in CONVERGENCE_SET if (shipped / f"{name}.py").is_file()
        )

        assert refrozen == []

    def test_every_converged_module_loads_from_pysmi(self):
        """Not merely absent from our tree -- actually resolved from pysmi's."""
        generated = pathlib.Path(
            importlib.util.find_spec("pysmi.mibs.pysnmp").submodule_search_locations[0]
        )
        for name in CONVERGENCE_SET:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                mibBuilder = builder.MibBuilder()
                mibBuilder.loadModules(name)

            origin = pathlib.Path(mibBuilder.getModulePath(name))

            assert origin.parent == generated, f"{name} loaded from {origin}"


class TestTheOneThatDidNotConverge:
    """Why SNMP-VIEW-BASED-ACM-MIB is still ours, checked rather than asserted
    in a comment."""

    def test_our_copy_exports_a_column_no_mib_declares(self):
        """If a MIB ever did declare it, the reason would evaporate."""
        assert "vacmContextStatus" in _load(HELD_BACK)
        assert "vacmContextStatus" not in _declared(HELD_BACK)

    def test_the_generated_table_has_only_the_column_rfc_3415_defines(self):
        """And the engine writes to the one it does not have.

        `addContext` addresses the column by sub-identifier rather than by
        name, which is why searching for the symbol finds nothing outside the
        MIB itself.
        """
        generated = pathlib.Path(
            importlib.util.find_spec("pysmi.mibs.pysnmp").submodule_search_locations[0]
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            mibBuilder = builder.MibBuilder()
            mibBuilder.setMibSources(
                builder.DirMibSource(str(generated)), *mibBuilder.getMibSources()
            )
            mibBuilder.loadModules(HELD_BACK)

        (entry,) = mibBuilder.importSymbols(HELD_BACK, "vacmContextEntry")
        root = entry.getName()
        columns = {
            node.getName()[len(root)]
            for node in mibBuilder.mibSymbols[HELD_BACK].values()
            if getattr(node, "getName", None)
            and node.getName()[: len(root)] == root
            and len(node.getName()) == len(root) + 1
        }

        assert columns == {1}
