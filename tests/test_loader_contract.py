"""What a generated MIB module may rely on when pysnmp loads it.

pysmi's ``PySnmpCodeGen`` emits Python that calls into ``MibBuilder`` and the
SMI classes. pysnmp has never stated what those calls may assume, so the
generator infers it -- ``getattr(mibBuilder, 'version', (0, 0, 0)) > (4, 4, 0)``
guards in emitted output, and a hand-kept list of classes believed to lack
``setReference()``. Inferences go stale silently: that list is wrong today, and
REFERENCE text is being dropped from generated modules because of it
(pysnmp/pysmi#194).

These tests are the executable half of the contract documented in
``docs/source/loader-contract.rst``. Anything asserted here is something a
generator targeting contract v1 may rely on, and changing it is a contract
change rather than an implementation detail.

They are characterization tests: they pin what pysnmp does today, so that the
written contract describes the code rather than an intention, and so that a
change to any of it is visible as a failure rather than as a downstream bug
months later.

See pysnmp/pysnmp#197.
"""

import pytest

from pysnmp.smi import error
from pysnmp.smi.builder import MibBuilder

#: Every setter named in the contract, by the class that must provide it. A
#: generator targeting contract v1 may emit any of these calls without guarding
#: on a pysnmp version.
CONTRACT_SETTERS = {
    "MibScalar": (
        "setDescription",
        "setLabel",
        "setMaxAccess",
        "setReference",
        "setStatus",
        "setSyntax",
        "setUnits",
    ),
    "MibTable": (
        "setDescription",
        "setLabel",
        "setMaxAccess",
        "setReference",
        "setStatus",
        "setSyntax",
        "setUnits",
    ),
    "MibTableRow": (
        "setDescription",
        "setIndexNames",
        "setLabel",
        "setMaxAccess",
        "setReference",
        "setStatus",
        "setSyntax",
        "setUnits",
    ),
    "MibTableColumn": (
        "setDescription",
        "setLabel",
        "setMaxAccess",
        "setReference",
        "setStatus",
        "setSyntax",
        "setUnits",
    ),
    "MibIdentifier": ("setLabel",),
    "ObjectIdentity": (
        "setDescription",
        "setLabel",
        "setReference",
        "setStatus",
    ),
    "NotificationType": (
        "setDescription",
        "setLabel",
        "setObjects",
        "setReference",
        "setStatus",
    ),
    "ModuleIdentity": (
        "setContactInfo",
        "setDescription",
        "setLabel",
        "setLastUpdated",
        "setOrganization",
        "setReference",
        "setRevisions",
        "setStatus",
    ),
}

#: The conformance classes, which live in SNMPv2-CONF rather than SNMPv2-SMI.
CONTRACT_SETTERS_CONF = {
    "ObjectGroup": (
        "setDescription",
        "setLabel",
        "setObjects",
        "setReference",
        "setStatus",
    ),
    "NotificationGroup": (
        "setDescription",
        "setLabel",
        "setObjects",
        "setReference",
        "setStatus",
    ),
    "ModuleCompliance": (
        "setDescription",
        "setLabel",
        "setObjects",
        "setReference",
        "setStatus",
    ),
    "AgentCapabilities": (
        "setDescription",
        "setLabel",
        "setProductRelease",
        "setReference",
        "setStatus",
    ),
}


@pytest.fixture(scope="module")
def mib_builder():
    """A builder with texts on, which is when the text setters are exercised."""
    builder = MibBuilder()
    builder.loadTexts = True

    return builder


@pytest.fixture(scope="module")
def smi_classes(mib_builder):
    names = tuple(CONTRACT_SETTERS)

    return dict(zip(names, mib_builder.importSymbols("SNMPv2-SMI", *names)))


@pytest.fixture(scope="module")
def conf_classes(mib_builder):
    names = tuple(CONTRACT_SETTERS_CONF)

    return dict(zip(names, mib_builder.importSymbols("SNMPv2-CONF", *names)))


class TestBuilderAttributes:
    """Attributes a generated module reads directly."""

    def test_version_is_present_and_is_a_tuple(self, mib_builder):
        """``version`` is always present, so ``getattr`` with a default is not needed.

        The default in ``getattr(mibBuilder, 'version', (0, 0, 0))`` exists
        because a generator could not assume the attribute. It can.
        """
        assert isinstance(mib_builder.version, tuple)
        assert all(isinstance(part, int) for part in mib_builder.version)

    def test_loader_contract_is_published(self, mib_builder):
        """``loaderContract`` is what a generator targets, in place of ``version``.

        The two move at different rates: ``version`` changes every release,
        ``loaderContract`` only when the contract does. A generator reading the
        wrong one re-acquires the staleness this contract exists to remove.
        """
        contract = mib_builder.loaderContract

        assert isinstance(contract, tuple)
        assert len(contract) == 2
        assert all(isinstance(part, int) for part in contract)
        assert contract >= (1, 0)

    def test_module_id_symbol_name(self, mib_builder):
        """``PYSNMP_MODULE_ID`` is the name a generated module exports the identity as."""
        assert mib_builder.moduleID == "PYSNMP_MODULE_ID"

    def test_load_texts_defaults_off(self):
        """A fresh builder discards texts, so the setters may be skipped."""
        assert MibBuilder().loadTexts is False


class TestSetters:
    """Every setter the contract names exists, on the class that must provide it."""

    def test_smi_classes_provide_their_setters(self, smi_classes):
        missing = {
            name: [
                setter
                for setter in setters
                if not callable(getattr(smi_classes[name], setter, None))
            ]
            for name, setters in CONTRACT_SETTERS.items()
        }

        assert {name: gap for name, gap in missing.items() if gap} == {}

    def test_conformance_classes_provide_their_setters(self, conf_classes):
        missing = {
            name: [
                setter
                for setter in setters
                if not callable(getattr(conf_classes[name], setter, None))
            ]
            for name, setters in CONTRACT_SETTERS_CONF.items()
        }

        assert {name: gap for name, gap in missing.items() if gap} == {}

    @pytest.mark.parametrize(
        "name", ["ObjectGroup", "NotificationGroup", "ModuleCompliance"]
    )
    def test_conformance_classes_accept_a_reference(self, conf_classes, name):
        """REFERENCE works on the conformance macros.

        pysmi suppresses it for exactly these three, believing they raise
        ``AttributeError`` under ``loadTexts=True``. They do not, and the
        suppression drops MIB text (pysnmp/pysmi#194). Asserted individually
        rather than as part of the sweep above because it is the case that
        motivated publishing this contract at all.
        """
        node = conf_classes[name]((1, 3, 6, 1, 4, 1, 99, 1))

        assert node.setReference("RFC 2580 section 4").getReference() == (
            "RFC 2580 section 4"
        )


class TestSetterContracts:
    """Setters return self, and round-trip through their getter."""

    def test_setters_return_self_for_chaining(self, smi_classes):
        """Generated code chains setters, so each must return the node."""
        node = smi_classes["MibScalar"]((1, 3, 6, 1, 4, 1, 99, 1), None)

        assert node.setStatus("current") is node
        assert node.setDescription("text") is node
        assert node.setMaxAccess("read-only") is node

    def test_object_lists_round_trip_as_module_symbol_pairs(self, conf_classes):
        """``setObjects`` takes ``(module, symbol)`` tuples and returns them."""
        group = conf_classes["ObjectGroup"]((1, 3, 6, 1, 4, 1, 99, 1)).setObjects(
            ("SNMPv2-MIB", "sysDescr"), ("SNMPv2-MIB", "sysUpTime")
        )

        assert group.getObjects() == (
            ("SNMPv2-MIB", "sysDescr"),
            ("SNMPv2-MIB", "sysUpTime"),
        )

    def test_index_names_round_trip_as_implied_module_symbol_triples(self, smi_classes):
        """``setIndexNames`` takes ``(implied, module, symbol)``, implied first."""
        row = smi_classes["MibTableRow"]((1, 3, 6, 1, 4, 1, 99, 1, 1)).setIndexNames(
            (0, "SNMPv2-MIB", "sysDescr"), (1, "SNMPv2-MIB", "sysName")
        )

        assert row.getIndexNames() == (
            (0, "SNMPv2-MIB", "sysDescr"),
            (1, "SNMPv2-MIB", "sysName"),
        )

    def test_module_identity_carries_its_timestamps(self, smi_classes):
        """``setLastUpdated`` and ``setRevisions`` take ASN.1 UTC strings verbatim."""
        identity = (
            smi_classes["ModuleIdentity"]((1, 3, 6, 1, 4, 1, 99))
            .setLastUpdated("200001010000Z")
            .setRevisions(("200001010000Z",))
        )

        assert identity.getLastUpdated() == "200001010000Z"
        assert identity.getRevisions() == ("200001010000Z",)


class TestExportSymbols:
    """``exportSymbols`` is how a generated module publishes what it defines."""

    def test_named_symbols_are_importable(self):
        builder = MibBuilder()
        node = builder.importSymbols("SNMPv2-SMI", "MibIdentifier")[0]((1, 3, 6, 1, 99))
        builder.exportSymbols("TEST-MIB", testNode=node)

        assert builder.importSymbols("TEST-MIB", "testNode") == (node,)

    def test_re_exporting_a_symbol_is_an_error(self):
        """A second export under the same name raises rather than overwriting."""
        builder = MibBuilder()
        MibIdentifier = builder.importSymbols("SNMPv2-SMI", "MibIdentifier")[0]
        builder.exportSymbols("TEST-MIB", testNode=MibIdentifier((1, 3, 6, 1, 99)))

        with pytest.raises(error.SmiError, match="already exported"):
            builder.exportSymbols("TEST-MIB", testNode=MibIdentifier((1, 3, 6, 1, 98)))

    def test_module_id_is_exported_under_its_own_name(self):
        """``PYSNMP_MODULE_ID`` is exempt from label rewriting.

        Every other exported symbol is renamed to its label when it has one;
        the module identity keeps the key it was exported under, which is what
        makes it findable.
        """
        builder = MibBuilder()
        identity = builder.importSymbols("SNMPv2-SMI", "ModuleIdentity")[0](
            (1, 3, 6, 1, 4, 1, 99)
        )
        builder.exportSymbols("TEST-MIB", PYSNMP_MODULE_ID=identity)

        assert builder.importSymbols("TEST-MIB", "PYSNMP_MODULE_ID") == (identity,)

    def test_importing_an_absent_symbol_raises(self):
        builder = MibBuilder()
        builder.exportSymbols("TEST-MIB")

        with pytest.raises(error.SmiError, match="No symbol"):
            builder.importSymbols("TEST-MIB", "absent")

    def test_importing_from_an_unknown_module_raises(self):
        with pytest.raises(error.MibNotFoundError):
            MibBuilder().importSymbols("NO-SUCH-MIB", "anything")

    def test_empty_module_name_is_refused(self):
        with pytest.raises(error.SmiError, match="empty MIB module name"):
            MibBuilder().importSymbols("", "anything")
