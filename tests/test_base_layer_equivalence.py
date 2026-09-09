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

from pysnmp.entity import config
from pysnmp.smi import builder
from tools.regenerate_mibs import ENGINE_MODULES

#: Modules the frozen tree and pysmi's bundle both carry. Eleven converged when
#: best-match selection made pysmi's copies reachable (pysnmp/pysnmp#198).
#:
#: The last five held out because they carried engine behaviour no code
#: generator can derive from ASN.1 -- an InetAddress index that reads a
#: preceding InetAddressType, an engine ID an implementation computes, a socket
#: address tuple, a tag's delimiter set. pysmi now splices that behaviour into
#: the module it generates (pysnmp/pysmi#231, #232), so the hand-edited copies
#: are gone and all sixteen are measured the same way.
CONVERGENCE_SET = (
    "INET-ADDRESS-MIB",
    "RFC1158-MIB",
    "RFC1213-MIB",
    "SNMP-COMMUNITY-MIB",
    "SNMP-FRAMEWORK-MIB",
    "SNMP-MPD-MIB",
    "SNMP-NOTIFICATION-MIB",
    "SNMP-PROXY-MIB",
    "SNMP-TARGET-MIB",
    "SNMP-USER-BASED-SM-MIB",
    "SNMP-USM-AES-MIB",
    "SNMP-USM-HMAC-SHA2-MIB",
    "SNMP-VIEW-BASED-ACM-MIB",
    "SNMPv2-MIB",
    "SNMPv2-TM",
    "TRANSPORT-ADDRESS-MIB",
)

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
#: ``vacmContextStatus``  A RowStatus column the frozen module added at
#:                         1.3.6.1.6.3.16.1.1.1.2 under a comment saying so --
#:                         *"The RowStatus column is not present in the MIB"*.
#:                         RFC 3415's vacmContextTable has one column and is
#:                         read-only. pysnmp/pysnmp#205 removed the engine's
#:                         dependency on it; see TestTheContextTableIsRfc3415.
DROPPED = {
    "RFC1213-MIB": {"TtcpInSegs"},
    "RFC1158-MIB": {"snmpInBadTypes", "snmpOutReadOnlys"},
    "SNMP-VIEW-BASED-ACM-MIB": {"vacmContextStatus"},
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
    ("SNMP-TARGET-MIB", "snmpTargetAddrName"),
    ("SNMP-TARGET-MIB", "snmpTargetParamsName"),
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

#: The syntax changes in the convergence set.
#:
#: RFC 1213 declares ``atNetAddress SYNTAX NetworkAddress``; RFC 1155 defines
#: NetworkAddress as ``CHOICE { internet IpAddress }`` -- a choice with exactly
#: one arm. The current generator resolves it to that arm. Same values either
#: way, and the constraint set widens from the choice-tag to IpAddress's own
#: sizes.
#:
#: RFC 3411 declares ``snmpEngineTime SYNTAX INTEGER (0..2147483647)`` and no
#: textual convention over it -- the module's only TCs are SnmpEngineID,
#: SnmpSecurityModel, SnmpMessageProcessingModel, SnmpSecurityLevel and
#: SnmpAdminString. The 2017 run named a ``SnmpEngineTime`` class anyway, which
#: ``test_no_dropped_symbol_is_declared_by_its_mib`` would not have caught
#: because the name was never exported. Integer32 is what the MIB says.
SYNTAX_CHANGES = {
    ("RFC1213-MIB", "atNetAddress"): ("NetworkAddress", "IpAddress"),
    ("SNMP-FRAMEWORK-MIB", "snmpEngineTime"): ("SnmpEngineTime", "Integer32"),
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

    assert sorted(frozen_modules) == sorted(CONVERGENCE_SET), (
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
    """The deletion itself, so it cannot be quietly undone.

    Seven of these modules are shipped by pysnmp again, and that is not a
    re-freeze. What made the 2017 tree a freeze was not that pysnmp shipped
    the files -- it was that they were hand-edited, stated no revision, and so
    took the tie against pysmi's copy and won it silently and for good.

    The seven are rendered by ``tools/regenerate_mibs.py`` from pysmi's own
    ASN.1 with pysmi's own code generator, they state a revision, and
    ``tests/test_generated_mibs.py`` fails the suite if a committed one stops
    matching its source. They are here so that an engine starts without pysmi
    installed, which is what makes ``pysnmp-pysmi`` an optional dependency.

    So what this class guards is narrower than it was, and is the part that
    actually mattered: nothing pysnmp ships may shadow pysmi silently, and
    nothing beyond the engine layer may be shipped at all.
    """

    def test_only_the_engine_layer_is_shipped_by_pysnmp(self):
        """Shipping a converged module beyond these seven is the old mistake.

        Each one is a copy that has to be kept current by hand or by tooling,
        and the reason to accept that cost for the engine layer -- an engine
        that starts with no pysmi -- does not extend to a module nothing on
        the start-up path loads.
        """
        shipped = pathlib.Path(builder.__file__).parent / "mibs"
        found = sorted(
            name for name in CONVERGENCE_SET if (shipped / f"{name}.py").is_file()
        )

        assert found == sorted(ENGINE_MODULES)

    @pytest.mark.parametrize("name", ENGINE_MODULES)
    def test_a_shipped_module_states_a_revision(self, name):
        """Without one it takes the tie against pysmi's copy on source order.

        Stating a revision is what makes the choice between two copies a
        comparison rather than an accident, so a shipped module that states
        none is the 2017 failure mode however it was produced.
        """
        shipped = pathlib.Path(builder.__file__).parent / "mibs" / f"{name}.py"

        assert "PYSNMP_MODULE_REVISION" in shipped.read_text(encoding="utf-8")

    def test_every_other_converged_module_loads_from_pysmi(self):
        """Not merely absent from our tree -- actually resolved from pysmi's."""
        generated = pathlib.Path(
            importlib.util.find_spec("pysmi.mibs.pysnmp").submodule_search_locations[0]
        )
        for name in CONVERGENCE_SET:
            if name in ENGINE_MODULES:
                continue

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                mibBuilder = builder.MibBuilder()
                mibBuilder.loadModules(name)

            origin = pathlib.Path(mibBuilder.getModulePath(name))

            assert origin.parent == generated, f"{name} loaded from {origin}"


class TestTheContextTableIsRfc3415:
    """The last module to converge, and what let it.

    `vacmContextTable` was the one place the frozen tree declared something no
    MIB does. `pysnmp.entity.config.addContext` created rows by writing
    `createAndGo` to that column, addressing it by sub-identifier rather than
    by name -- which is why searching for the symbol found nothing outside the
    MIB itself, and why the dependency survived unnoticed.
    """

    def test_no_mib_declares_the_column_the_frozen_copy_added(self):
        """The premise for dropping it, parsed rather than asserted here."""
        assert "vacmContextStatus" not in _declared("SNMP-VIEW-BASED-ACM-MIB")

    def test_the_table_has_only_the_column_rfc_3415_defines(self):
        """One column, `vacmContextName`, at sub-identifier 1."""
        entry = _load("SNMP-VIEW-BASED-ACM-MIB")["vacmContextEntry"]
        root = entry.getName()
        columns = {
            node.getName()[len(root)]
            for node in _load("SNMP-VIEW-BASED-ACM-MIB").values()
            if getattr(node, "getName", None)
            and node.getName()[: len(root)] == root
            and len(node.getName()) == len(root) + 1
        }

        assert columns == {1}

    def test_the_column_is_read_only(self):
        """Which is why a row cannot be created by writing to it.

        RFC 3415 says the table "is read-only. It cannot be configured via
        SNMP", so `addContext` registers the row on the column as a managed
        object instance instead of going through the SET machinery.
        """
        column = _load("SNMP-VIEW-BASED-ACM-MIB")["vacmContextName"]

        assert column.maxAccess == "readonly"


class TestContextsStillWork:
    """`addContext` and `delContext` against the converged module."""

    @staticmethod
    def _contexts(snmpEngine):
        """Every context name the table currently holds, walked as VACM does.

        `pysnmp.proto.acmod.rfc3415` reads the table only this way -- stepping
        `vacmContextName` with `getNextNode` -- so this is the view that has to
        be right.
        """
        mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder
        (column,) = mibBuilder.importSymbols(
            "SNMP-VIEW-BASED-ACM-MIB", "vacmContextName"
        )

        found, node = [], column
        while True:
            try:
                node = column.getNextNode(node.name)

            except Exception:
                break

            found.append(node.syntax.prettyPrint())

        return found

    @pytest.fixture
    def engine(self):
        from pysnmp.entity import engine as engine_module

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            return engine_module.SnmpEngine()

    def test_an_added_context_is_visible_to_the_walk(self, engine):
        config.addContext(engine, "watermelon")

        assert "watermelon" in self._contexts(engine)

    def test_adding_the_same_context_twice_is_not_an_error(self, engine):
        """The RowStatus sequence this replaces destroyed before creating, so
        re-adding was already supported and stays supported."""
        config.addContext(engine, "watermelon")
        config.addContext(engine, "watermelon")

        assert self._contexts(engine).count("watermelon") == 1

    def test_a_deleted_context_is_gone(self, engine):
        config.addContext(engine, "watermelon")
        config.delContext(engine, "watermelon")

        assert "watermelon" not in self._contexts(engine)

    def test_deleting_a_context_that_was_never_added_is_silent(self, engine):
        """As writing `destroy` to a non-existent row was."""
        config.delContext(engine, "never-added")
