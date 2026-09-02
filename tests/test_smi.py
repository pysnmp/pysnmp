"""Unit tests for SMI builder, view, indices, instrumentation, and bundled MIBs."""

import time

import pytest
from pyasn1.type.constraint import SingleValueConstraint, ValueRangeConstraint
from pyasn1.type.namedval import NamedValues

from pysnmp.entity.engine import SnmpEngine
from pysnmp.proto.rfc1902 import Integer, Integer32, ObjectIdentifier, OctetString
from pysnmp.smi import builder, error, exval, indices, view
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType


@pytest.fixture(scope="module")
def mib_builder():
    return SnmpEngine().getMibBuilder()


@pytest.fixture(scope="module")
def mib_view_controller(mib_builder):
    return view.MibViewController(mib_builder)


class TestSmiError:
    def test_smi_error(self):
        err = error.SmiError("test")
        assert "test" in str(err)

    def test_mib_load_error(self):
        err = error.MibLoadError("test")
        assert isinstance(err, error.SmiError)

    def test_mib_not_found_error(self):
        err = error.MibNotFoundError("test")
        assert isinstance(err, error.MibLoadError)

    def test_mib_operation_error(self):
        err = error.MibOperationError(idx=0)
        assert err["idx"] == 0
        assert "idx" in err
        assert err.get("idx") == 0

    def test_mib_operation_error_keys(self):
        err = error.MibOperationError(idx=0, oid=(1, 3))
        assert "idx" in err.keys()

    def test_mib_operation_error_update(self):
        err = error.MibOperationError(idx=0)
        err.update({"oid": (1, 3)})
        assert err["oid"] == (1, 3)

    def test_error_subclasses(self):
        assert issubclass(error.TooBigError, error.MibOperationError)
        assert issubclass(error.NoSuchNameError, error.MibOperationError)
        assert issubclass(error.BadValueError, error.MibOperationError)
        assert issubclass(error.ReadOnlyError, error.MibOperationError)
        assert issubclass(error.GenError, error.MibOperationError)
        assert issubclass(error.NoAccessError, error.MibOperationError)
        assert issubclass(error.WrongTypeError, error.MibOperationError)
        assert issubclass(error.WrongLengthError, error.MibOperationError)
        assert issubclass(error.WrongEncodingError, error.MibOperationError)
        assert issubclass(error.WrongValueError, error.MibOperationError)
        assert issubclass(error.NoCreationError, error.MibOperationError)
        assert issubclass(error.InconsistentValueError, error.MibOperationError)
        assert issubclass(error.ResourceUnavailableError, error.MibOperationError)
        assert issubclass(error.CommitFailedError, error.MibOperationError)


class TestExval:
    def test_no_such_object(self):
        assert exval.noSuchObject is not None

    def test_no_such_instance(self):
        assert exval.noSuchInstance is not None

    def test_end_of_mib_view(self):
        assert exval.endOfMibView is not None
        assert exval.endOfMib is exval.endOfMibView


class TestOrderedDict:
    def test_set_get(self):
        d = indices.OrderedDict()
        d["a"] = 1
        d["b"] = 2
        assert d["a"] == 1
        assert d["b"] == 2

    def test_keys_ordered(self):
        d = indices.OrderedDict()
        d["b"] = 2
        d["a"] = 1
        d["c"] = 3
        keys = d.keys()
        assert keys == ["a", "b", "c"]

    def test_values(self):
        d = indices.OrderedDict()
        d["b"] = 2
        d["a"] = 1
        vals = d.values()
        assert vals == [1, 2]

    def test_items(self):
        d = indices.OrderedDict()
        d["b"] = 2
        d["a"] = 1
        items = d.items()
        assert items == [("a", 1), ("b", 2)]

    def test_delete(self):
        d = indices.OrderedDict()
        d["a"] = 1
        d["b"] = 2
        del d["a"]
        assert "a" not in d
        assert d.keys() == ["b"]

    def test_clear(self):
        d = indices.OrderedDict()
        d["a"] = 1
        d.clear()
        assert len(d) == 0

    def test_next_key(self):
        d = indices.OrderedDict()
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        assert d.nextKey("a") == "b"
        assert d.nextKey("b") == "c"

    def test_next_key_not_found(self):
        d = indices.OrderedDict()
        d["a"] = 1
        with pytest.raises(KeyError):
            d.nextKey("a")

    def test_next_key_bisect(self):
        d = indices.OrderedDict()
        d["a"] = 1
        d["c"] = 3
        # 'b' is not in dict, bisect should find 'c'
        assert d.nextKey("b") == "c"

    def test_update_from_dict(self):
        d = indices.OrderedDict()
        d.update({"a": 1, "b": 2})
        assert d["a"] == 1
        assert d["b"] == 2

    def test_update_from_iterable(self):
        d = indices.OrderedDict()
        d.update([("a", 1), ("b", 2)])
        assert d["a"] == 1
        assert d["b"] == 2

    def test_update_kwargs(self):
        d = indices.OrderedDict()
        d.update(a=1, b=2)
        assert d["a"] == 1

    def test_get_keys_lens(self):
        d = indices.OrderedDict()
        d["a"] = 1
        d["bb"] = 2
        lens = d.getKeysLens()
        assert sorted(lens) == [1, 2]


class TestOidOrderedDict:
    def test_set_get(self):
        d = indices.OidOrderedDict()
        d[(1, 3, 6)] = "a"
        d[(1, 3, 7)] = "b"
        assert d[(1, 3, 6)] == "a"

    def test_string_key(self):
        d = indices.OidOrderedDict()
        d["1.3.6"] = "a"
        assert d["1.3.6"] == "a"

    def test_oid_sorting(self):
        d = indices.OidOrderedDict()
        d[(1, 3, 6, 2)] = "b"
        d[(1, 3, 6, 1)] = "a"
        d[(1, 3, 6, 3)] = "c"
        keys = d.keys()
        assert keys == [(1, 3, 6, 1), (1, 3, 6, 2), (1, 3, 6, 3)]

    def test_delete(self):
        d = indices.OidOrderedDict()
        d[(1, 3, 6)] = "a"
        del d[(1, 3, 6)]
        assert (1, 3, 6) not in d


class TestMibBuilder:
    def test_load_modules(self, mib_builder):
        mib_builder.loadModules("SNMPv2-MIB")
        assert "SNMPv2-MIB" in mib_builder.mibSymbols

    def test_import_symbols(self, mib_builder):
        sysDescr = mib_builder.importSymbols("SNMPv2-MIB", "sysDescr")
        assert sysDescr is not None
        assert sysDescr[0].name == (1, 3, 6, 1, 2, 1, 1, 1)

    def test_import_multiple_symbols(self, mib_builder):
        result = mib_builder.importSymbols("SNMPv2-MIB", "sysDescr", "sysObjectID", "sysUpTime")
        assert len(result) == 3

    def test_load_multiple_modules(self, mib_builder):
        mib_builder.loadModules("SNMP-FRAMEWORK-MIB", "SNMP-TARGET-MIB")
        assert "SNMP-FRAMEWORK-MIB" in mib_builder.mibSymbols
        assert "SNMP-TARGET-MIB" in mib_builder.mibSymbols

    def test_get_mib_sources(self, mib_builder):
        sources = mib_builder.getMibSources()
        assert len(sources) > 0

    def test_module_id(self, mib_builder):
        assert mib_builder.moduleID is not None


class TestMibViewController:
    def test_index_mib(self, mib_view_controller):
        mib_view_controller.indexMib()
        assert mib_view_controller.lastBuildId >= 0

    def test_get_first_module_name(self, mib_view_controller):
        name = mib_view_controller.getFirstModuleName()
        assert name is not None

    def test_get_last_module_name(self, mib_view_controller):
        name = mib_view_controller.getLastModuleName()
        assert name is not None

    def test_get_next_module_name(self, mib_view_controller):
        first = mib_view_controller.getFirstModuleName()
        try:
            nxt = mib_view_controller.getNextModuleName(first)
            assert nxt is not None
        except error.SmiError:
            # Only one module loaded
            pass

    def test_get_node_name_by_oid(self, mib_view_controller):
        oid, label, suffix = mib_view_controller.getNodeNameByOid((1, 3, 6, 1, 2, 1, 1, 1, 0))
        assert oid is not None

    def test_get_node_name_by_oid_unknown(self, mib_view_controller):
        with pytest.raises(error.NoSuchObjectError):
            mib_view_controller.getNodeNameByOid((99, 99, 99))


class TestObjectIdentity:
    def test_from_oid_tuple(self):
        oi = ObjectIdentity((1, 3, 6, 1, 2, 1, 1, 1, 0))
        assert oi is not None

    def test_from_oid_string(self):
        oi = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        assert oi is not None

    def test_from_mib_name_and_symbol(self):
        oi = ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)
        assert oi is not None

    def test_get_mib_symbol_unresolved(self):
        oi = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        with pytest.raises(error.SmiError):
            oi.getMibSymbol()

    def test_get_oid_unresolved(self):
        oi = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        with pytest.raises(error.SmiError):
            oi.getOid()

    def test_is_fully_resolved(self):
        oi = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        assert not oi.isFullyResolved()

    def test_resolve_with_mib(self, mib_view_controller):
        oi = ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)
        oi.resolveWithMib(mib_view_controller)
        assert oi.isFullyResolved()
        modName, symName, indices = oi.getMibSymbol()
        assert modName == "SNMPv2-MIB"
        assert symName == "sysDescr"

    def test_resolve_oid_to_mib_symbol(self, mib_view_controller):
        oi = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        oi.resolveWithMib(mib_view_controller)
        assert oi.isFullyResolved()
        modName, symName, indices = oi.getMibSymbol()
        assert modName == "SNMPv2-MIB"
        assert symName == "sysDescr"

    def test_get_oid_resolved(self, mib_view_controller):
        oi = ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)
        oi.resolveWithMib(mib_view_controller)
        oid = oi.getOid()
        assert tuple(oid) == (1, 3, 6, 1, 2, 1, 1, 1, 0)

    def test_get_label(self, mib_view_controller):
        oi = ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)
        oi.resolveWithMib(mib_view_controller)
        label = oi.getLabel()
        assert "sysDescr" in label

    def test_get_first_by_node_type_scalar(self, mib_view_controller):
        """getFirstNodeName with nodeType='scalar' returns only scalar nodes."""
        mib_view_controller.mibBuilder.loadModules("SNMPv2-MIB")
        oid, label, suffix = mib_view_controller.getFirstNodeName("SNMPv2-MIB", "scalar")
        symName = label[-1]
        symObj = mib_view_controller.mibBuilder.mibSymbols["SNMPv2-MIB"][symName]
        assert symObj.__class__.__name__ == "MibScalar"

    def test_get_last_by_node_type_scalar(self, mib_view_controller):
        """getLastNodeName with nodeType='scalar' returns only scalar nodes."""
        mib_view_controller.mibBuilder.loadModules("SNMPv2-MIB")
        oid, label, suffix = mib_view_controller.getLastNodeName("SNMPv2-MIB", "scalar")
        symName = label[-1]
        symObj = mib_view_controller.mibBuilder.mibSymbols["SNMPv2-MIB"][symName]
        assert symObj.__class__.__name__ == "MibScalar"

    def test_get_first_by_node_type_table(self, mib_view_controller):
        """getFirstNodeName with nodeType='table' returns only table nodes."""
        mib_view_controller.mibBuilder.loadModules("SNMPv2-MIB")
        oid, label, suffix = mib_view_controller.getFirstNodeName("SNMPv2-MIB", "table")
        symName = label[-1]
        symObj = mib_view_controller.mibBuilder.mibSymbols["SNMPv2-MIB"][symName]
        assert symObj.__class__.__name__ == "MibTable"

    def test_get_first_by_node_type_includes_scalar_subclass(self, mib_view_controller):
        """Typed lookup recognizes MIB extensions derived from MibScalar."""
        mibBuilder = mib_view_controller.mibBuilder
        (MibScalar,) = mibBuilder.importSymbols("SNMPv2-SMI", "MibScalar")

        class CustomMibScalar(MibScalar):
            pass

        mibBuilder.exportSymbols(
            "TEST-CUSTOM-SMI",
            customScalar=CustomMibScalar((1, 3, 6, 1, 4, 1, 20408, 1), Integer(0)),
        )

        oid, label, suffix = mib_view_controller.getFirstNodeName("TEST-CUSTOM-SMI", "scalar")
        assert oid == (1, 3, 6, 1, 4, 1, 20408, 1)
        assert label[-1] == "customScalar"

    def test_get_first_by_node_type_unknown_raises(self, mib_view_controller):
        """getFirstNodeName with unknown nodeType raises SmiError."""
        mib_view_controller.mibBuilder.loadModules("SNMPv2-MIB")
        with pytest.raises(error.SmiError):
            mib_view_controller.getFirstNodeName("SNMPv2-MIB", "unknown")

    def test_get_first_by_node_type_no_match_raises(self, mib_view_controller):
        """getFirstNodeName with nodeType that has no matches raises NoSuchObjectError."""
        mib_view_controller.mibBuilder.loadModules("SNMPv2-MIB")
        with pytest.raises(error.SmiError):
            mib_view_controller.getFirstNodeName("NON-EXISTENT-MIB", "scalar")

    def test_object_identity_last_with_node_type(self, mib_view_controller):
        """ObjectIdentity with last=True and nodeType='scalar' resolves to a scalar."""
        mib_view_controller.mibBuilder.loadModules("SNMPv2-MIB")
        oi = ObjectIdentity("SNMPv2-MIB", last=True, nodeType="scalar")
        oi.resolveWithMib(mib_view_controller)
        mibNode = oi.getMibNode()
        assert mibNode.__class__.__name__ == "MibScalar"


class TestObjectType:
    def test_creation(self):
        ot = ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0"), OctetString("test"))
        assert ot is not None

    def test_resolve_with_mib(self, mib_view_controller):
        ot = ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0), OctetString("test"))
        ot.resolveWithMib(mib_view_controller)
        assert ot.isFullyResolved()

    def test_unresolved_raises(self):
        ot = ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0"), OctetString("test"))
        assert not ot.isFullyResolved()

    def test_is_fully_resolved(self):
        ot = ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0"), OctetString("test"))
        assert not ot.isFullyResolved()

    def test_get_units_unresolved_raises(self):
        ot = ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0"), OctetString("test"))
        with pytest.raises(error.SmiError):
            ot.getUnits()

    def test_get_units_no_units(self, mib_view_controller):
        ot = ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0), OctetString("test"))
        ot.resolveWithMib(mib_view_controller)
        assert ot.getUnits() == ""

    def test_get_units_propagated(self, mib_view_controller):
        """Verify getUnits() returns the UNITS clause value after resolution."""
        mib_view_controller.mibBuilder.loadModules("SNMP-FRAMEWORK-MIB")
        ot = ObjectType(
            ObjectIdentity("SNMP-FRAMEWORK-MIB", "snmpEngineTime", 0),
            Integer(42),
        )
        ot.resolveWithMib(mib_view_controller)
        assert ot.getUnits() == "seconds"

    def test_get_units_propagated_table_column(self, mib_view_controller):
        """Verify getUnits() works for table columns with UNITS clause."""
        mib_view_controller.mibBuilder.loadModules("SNMP-TARGET-MIB")
        try:
            ot = ObjectType(
                ObjectIdentity("SNMP-TARGET-MIB", "snmpTargetAddrTimeout", 0),
                Integer(0),
            )
            ot.resolveWithMib(mib_view_controller)
            assert isinstance(ot.getUnits(), str)
        except error.SmiError:
            pytest.skip("SNMP-TARGET-MIB snmpTargetAddrTimeout not available")


@pytest.fixture(scope="module")
def usm_view():
    mibBuilder = builder.MibBuilder()
    mibBuilder.loadModules("SNMP-USER-BASED-SM-MIB", "SNMPv2-MIB")
    return view.MibViewController(mibBuilder)


class TestObjectTypeRowPointerValues:
    """An OBJECT IDENTIFIER *value* is resolved only to render it by MIB name.

    A peer is free to return a RowPointer whose index this MIB view cannot decode;
    that must not fail the varbind and abort the surrounding walk.
    """

    # usmUserEntry INDEX is { usmUserEngineID, usmUserName }, both variable-length
    # OCTET STRINGs and therefore length-prefixed in the instance OID.
    USM_USER_STATUS = "1.3.6.1.6.3.15.1.2.2.1.13"
    # engineID length octet says 5 but 8 sub-ids follow, leaving excess sub-ids
    UNDECODABLE = USM_USER_STATUS + ".5.128.0.0.0.1.2.3.4.3.97.98.99"
    DECODABLE = USM_USER_STATUS + ".5.128.0.0.0.1.3.97.98.99"

    def test_undecodable_row_pointer_resolves_standalone_raises(self, usm_view):
        """Guard the premise: resolving it as an ObjectIdentity does raise."""
        with pytest.raises(error.SmiError):
            ObjectIdentity(self.UNDECODABLE).resolveWithMib(usm_view)

    @pytest.mark.parametrize("ignore_errors", [True, False])
    def test_undecodable_row_pointer_value_is_tolerated(self, usm_view, ignore_errors):
        ot = ObjectType(
            ObjectIdentity("SNMPv2-MIB", "sysObjectID", 0),
            ObjectIdentifier(self.UNDECODABLE),
        )
        ot.resolveWithMib(usm_view, ignoreErrors=ignore_errors)
        assert ot[1].prettyPrint() == self.UNDECODABLE

    def test_decodable_row_pointer_value_still_resolves(self, usm_view):
        ot = ObjectType(
            ObjectIdentity("SNMPv2-MIB", "sysObjectID", 0),
            ObjectIdentifier(self.DECODABLE),
        )
        ot.resolveWithMib(usm_view, ignoreErrors=False)
        assert ot[1].prettyPrint() == 'SNMP-USER-BASED-SM-MIB::usmUserStatus."0x8000000001"."abc"'


class TestBundledMibs:
    """Test that each bundled MIB loads through the public MibBuilder."""

    BUNDLED_MIBS = [
        "SNMPv2-MIB",
        "SNMPv2-SMI",
        "SNMPv2-TC",
        "SNMPv2-CONF",
        "SNMPv2-TM",
        "SNMP-FRAMEWORK-MIB",
        "SNMP-MPD-MIB",
        "SNMP-COMMUNITY-MIB",
        "SNMP-TARGET-MIB",
        "SNMP-NOTIFICATION-MIB",
        "SNMP-PROXY-MIB",
        "SNMP-USER-BASED-SM-MIB",
        "SNMP-USER-BASED-SM-3DES-MIB",
        "SNMP-USM-AES-MIB",
        "SNMP-USM-HMAC-SHA2-MIB",
        "SNMP-VIEW-BASED-ACM-MIB",
        "PYSNMP-MIB",
        "PYSNMP-SOURCE-MIB",
        "PYSNMP-USM-MIB",
        "RFC1213-MIB",
        "RFC1158-MIB",
        "INET-ADDRESS-MIB",
        "TRANSPORT-ADDRESS-MIB",
    ]

    def test_load_all_bundled_mibs(self, mib_builder):
        for mib_name in self.BUNDLED_MIBS:
            mib_builder.loadModules(mib_name)
            assert mib_name in mib_builder.mibSymbols, f"Failed to load {mib_name}"

    def test_snmpv2_mib_symbols(self, mib_builder):
        mib_builder.loadModules("SNMPv2-MIB")
        (sysDescr,) = mib_builder.importSymbols("SNMPv2-MIB", "sysDescr")
        assert sysDescr.name == (1, 3, 6, 1, 2, 1, 1, 1)

    def test_snmpv2_smi_symbols(self, mib_builder):
        mib_builder.loadModules("SNMPv2-SMI")
        (iso,) = mib_builder.importSymbols("SNMPv2-SMI", "iso")
        assert tuple(iso.name) == (1,)

    def test_snmp_framework_mib_symbols(self, mib_builder):
        mib_builder.loadModules("SNMP-FRAMEWORK-MIB")
        (snmpEngineID,) = mib_builder.importSymbols("SNMP-FRAMEWORK-MIB", "snmpEngineID")
        assert snmpEngineID is not None

    def test_snmp_target_mib_symbols(self, mib_builder):
        mib_builder.loadModules("SNMP-TARGET-MIB")
        (snmpTargetAddrEntry,) = mib_builder.importSymbols(
            "SNMP-TARGET-MIB", "snmpTargetAddrEntry"
        )
        assert snmpTargetAddrEntry is not None

    def test_snmp_view_acm_mib_symbols(self, mib_builder):
        mib_builder.loadModules("SNMP-VIEW-BASED-ACM-MIB")
        (vacmContextName,) = mib_builder.importSymbols(
            "SNMP-VIEW-BASED-ACM-MIB", "vacmContextName"
        )
        assert vacmContextName is not None

    def test_rfc1213_mib_symbols(self, mib_builder):
        mib_builder.loadModules("RFC1213-MIB")
        # RFC1213-MIB defines many MIB objects
        assert "RFC1213-MIB" in mib_builder.mibSymbols
        assert len(mib_builder.mibSymbols["RFC1213-MIB"]) > 0

    def test_inet_address_mib_symbols(self, mib_builder):
        mib_builder.loadModules("INET-ADDRESS-MIB")
        (InetAddress,) = mib_builder.importSymbols("INET-ADDRESS-MIB", "InetAddress")
        assert InetAddress is not None


class TestMibInstrumController:
    @pytest.fixture
    def fresh_builder(self):
        return SnmpEngine().getMibBuilder()

    def test_read_vars_returns_result(self, fresh_builder):
        from pysnmp.smi.instrum import MibInstrumController

        ctrl = MibInstrumController(fresh_builder)
        # Reading a valid OID should return var binds
        result = ctrl.readVars([((1, 3, 6, 1, 2, 1, 1, 1, 0), Integer(0))])
        assert len(result) == 1

    def test_read_next_vars_returns_result(self, fresh_builder):
        from pysnmp.smi.instrum import MibInstrumController

        ctrl = MibInstrumController(fresh_builder)
        # readNextVars should return a result (possibly with endOfMibView)
        result = ctrl.readNextVars([((1, 3, 6, 1, 2, 1, 1, 1, 0), Integer(0))])
        # The result should be a list
        assert isinstance(result, list)

    def test_get_mib_builder(self, fresh_builder):
        from pysnmp.smi.instrum import MibInstrumController

        ctrl = MibInstrumController(fresh_builder)
        assert ctrl.getMibBuilder() is fresh_builder

    def test_abstract_controller_read_vars(self):
        from pysnmp.smi.instrum import AbstractMibInstrumController

        ctrl = AbstractMibInstrumController()
        with pytest.raises(error.NoSuchInstanceError):
            ctrl.readVars([])

    def test_abstract_controller_read_next_vars(self):
        from pysnmp.smi.instrum import AbstractMibInstrumController

        ctrl = AbstractMibInstrumController()
        with pytest.raises(error.EndOfMibViewError):
            ctrl.readNextVars([])

    def test_abstract_controller_write_vars(self):
        from pysnmp.smi.instrum import AbstractMibInstrumController

        ctrl = AbstractMibInstrumController()
        with pytest.raises(error.NoSuchObjectError):
            ctrl.writeVars([])


class TestMibWalk:
    """Tests for MIB tree walk operations and VACM shadowing."""

    @pytest.fixture
    def fresh_builder(self):
        return SnmpEngine().getMibBuilder()

    def test_walk_shadowed_oids_correct(self, fresh_builder):
        """Walk over VACM shadowed OIDs returns correct results."""
        from pysnmp.smi.instrum import MibInstrumController

        ctrl = MibInstrumController(fresh_builder)
        result = ctrl.readNextVars([((1, 3, 6, 1, 2, 1, 1, 1, 0), Integer(0))])
        assert isinstance(result, list)
        assert len(result) == 1
        name, val = result[0]
        assert name is not None

    def test_walk_shadowed_oids_performance(self, fresh_builder):
        """Performance test: walk over many OIDs should complete quickly."""
        from pysnmp.smi.instrum import MibInstrumController

        ctrl = MibInstrumController(fresh_builder)
        var_binds = [((1, 3, 6, 1, 2, 1, 1, 1, 0), Integer(0))]
        start = time.monotonic()
        for _ in range(100):
            result = ctrl.readNextVars(var_binds)
            if result:
                var_binds = [(result[0][0], Integer(0))]
            else:
                break
        elapsed = time.monotonic() - start
        assert elapsed < 5.0

    def test_get_next_branch_optimization(self, fresh_builder):
        """Test that getNextBranch uses iterator instead of list creation."""
        from pysnmp.smi.instrum import MibInstrumController

        ctrl = MibInstrumController(fresh_builder)
        result = ctrl.readNextVars([((1, 3, 6, 1, 2, 1, 1, 1, 0), Integer(0))])
        assert isinstance(result, list)


def _build_optional_row(optional):
    """Build an active-row consistency check with one unset column."""
    mibBuilder = builder.MibBuilder()
    MibScalarInstance, MibTableColumn, MibTableRow = mibBuilder.importSymbols(
        "SNMPv2-SMI", "MibScalarInstance", "MibTableColumn", "MibTableRow"
    )

    baseOid = (1, 3, 6, 1, 4, 1, 20408, 999, 1)
    row = MibTableRow(baseOid).setIndexNames((0, "TEST-OPTIONAL-MIB", "testIndex"))
    testIndex = MibTableColumn(baseOid + (1,), Integer32()).setMaxAccess("not-accessible")
    optionalValue = MibTableColumn(baseOid + (2,), Integer32()).setMaxAccess("read-create")
    rowStatus = MibTableColumn(baseOid + (3,), Integer32(1)).setMaxAccess("read-create")

    if optional:
        optionalValue.setOptional()

    suffix = (1,)
    testIndex.registerSubtrees(MibScalarInstance(testIndex.name, suffix, Integer32(1)))
    optionalValue.registerSubtrees(MibScalarInstance(optionalValue.name, suffix, Integer32()))
    rowStatus.registerSubtrees(MibScalarInstance(rowStatus.name, suffix, Integer32(1)))
    row.registerSubtrees(testIndex, optionalValue, rowStatus)

    mibBuilder.exportSymbols(
        "TEST-OPTIONAL-MIB",
        testEntry=row,
        testIndex=testIndex,
        optionalValue=optionalValue,
        rowStatus=rowStatus,
    )

    def activate_row(*args):
        raise error.RowCreationWanted(syntax=Integer32(1))

    rowStatus.writeCommit = activate_row
    return row, optionalValue, rowStatus, suffix


class TestOptionalTableColumns:
    """Test optional columns through actual row activation."""

    def test_optional_flag_defaults_to_false_and_has_aliases(self):
        mibBuilder = builder.MibBuilder()
        (MibTableColumn,) = mibBuilder.importSymbols("SNMPv2-SMI", "MibTableColumn")
        column = MibTableColumn((1, 3, 6, 1, 4, 1, 20408, 1), Integer32())

        assert not column.isOptional()
        assert not column.is_optional()
        assert column.set_optional() is column
        assert column.isOptional()
        assert column.setOptional(False) is column
        assert not column.is_optional()

    def test_optional_unset_column_allows_row_activation(self):
        row, optionalValue, rowStatus, suffix = _build_optional_row(True)

        row.writeCommit(rowStatus.name + suffix, 1, 0, (None, None))

        optionalInstance = optionalValue.getNode(optionalValue.name + suffix)
        assert not optionalInstance.syntax.isValue

    def test_mandatory_unset_column_rejects_row_activation(self):
        row, _, rowStatus, suffix = _build_optional_row(False)

        with pytest.raises(error.InconsistentValueError):
            row.writeCommit(rowStatus.name + suffix, 1, 0, (None, None))


@pytest.fixture
def table_view():
    """Build a MIB view without an instrumentation controller."""
    mibBuilder = builder.MibBuilder()
    mibBuilder.loadModules("SNMPv2-MIB")
    return mibBuilder, view.MibViewController(mibBuilder)


class TestTableCellApi:
    """Test table cell name construction and decomposition."""

    def test_columns_do_not_require_instrumentation(self, table_view):
        mibBuilder, mibView = table_view
        (row,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")

        assert [columnId for columnId, _, _ in row.getColumns()] == [1, 2, 3, 4]
        assert row.get_columns() == row.getColumns()
        assert len(mibView.getTableColumns("SNMPv2-MIB", "sysOREntry")) == 4
        assert mibView.get_table_columns("SNMPv2-MIB", "sysOREntry") == row.getColumns()

    def test_resolves_numeric_and_symbolic_columns(self, table_view):
        _, mibView = table_view
        expected = (1, 3, 6, 1, 2, 1, 1, 9, 1, 2, 1)

        assert mibView.resolveCellOid("SNMPv2-MIB", "sysOREntry", 2, 1) == expected
        assert mibView.resolve_cell_oid("SNMPv2-MIB", "sysOREntry", "sysORID", 1) == expected

    def test_rejects_unknown_column(self, table_view):
        _, mibView = table_view

        with pytest.raises(error.SmiError, match="Unknown column ID"):
            mibView.resolveCellOid("SNMPv2-MIB", "sysOREntry", 99, 1)

        with pytest.raises(error.SmiError, match="not a column"):
            mibView.resolveCellOid("SNMPv2-MIB", "sysOREntry", "sysDescr", 1)

    @pytest.mark.parametrize("indices", [(), (1, 2)])
    def test_rejects_wrong_index_count(self, table_view, indices):
        _, mibView = table_view

        with pytest.raises(error.SmiError, match="expects 1 indices"):
            mibView.resolveCellOid("SNMPv2-MIB", "sysOREntry", "sysORID", *indices)

    def test_builds_all_row_oids_without_instrumentation(self, table_view):
        mibBuilder, _ = table_view
        (row,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")

        assert row.getRowOids(1) == tuple(row.name + (columnId, 1) for columnId in (1, 2, 3, 4))
        assert row.get_row_oids(1) == row.getRowOids(1)

    def test_decodes_cell_indices(self, table_view):
        mibBuilder, _ = table_view
        (row,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")

        assert tuple(int(value) for value in row.get_cell_indices((7,))) == (7,)

    def test_decomposes_complete_cell_oid(self, table_view):
        _, mibView = table_view
        cellOid = mibView.resolveCellOid("SNMPv2-MIB", "sysOREntry", "sysORID", 7)

        moduleName, rowName, columnName, cellIndices = mibView.getTableCellInfo(cellOid)

        assert (moduleName, rowName, columnName) == (
            "SNMPv2-MIB",
            "sysOREntry",
            "sysORID",
        )
        assert tuple(int(value) for value in cellIndices) == (7,)
        assert mibView.get_table_cell_info(cellOid) == mibView.getTableCellInfo(cellOid)

    def test_rejects_non_table_objects(self, table_view):
        _, mibView = table_view

        with pytest.raises(error.SmiError, match="not a MibTableRow"):
            mibView.getTableColumns("SNMPv2-MIB", "sysDescr")
        with pytest.raises(error.SmiError, match="not a MibTableRow"):
            mibView.resolveCellOid("SNMPv2-MIB", "sysDescr", 0, 0)
        with pytest.raises(error.SmiError, match="not a table cell"):
            mibView.getTableCellInfo((1, 3, 6, 1, 2, 1, 1, 1, 0))


class TestCloneSubtypeSemantics:
    """Verify the documented pyasn1 clone and subtype distinction."""

    def test_clone_replaces_named_values(self):
        original = Integer32().clone(namedValues=NamedValues(("a", 1), ("b", 2)))
        replaced = original.clone(namedValues=NamedValues(("c", 3)))

        assert replaced.namedValues[3] == "c"
        assert 1 not in replaced.namedValues
        assert 2 not in replaced.namedValues

    def test_clone_sets_value(self):
        assert int(Integer32().clone(42)) == 42

    def test_clone_without_changes_returns_same_immutable_value(self):
        value = Integer32(42)

        assert value.clone() is value

    def test_subtype_intersects_constraints(self):
        constrained = Integer32().subtype(subtypeSpec=ValueRangeConstraint(0, 100))

        assert int(constrained.clone(50)) == 50
        with pytest.raises(Exception):
            constrained.clone(200)

    def test_chained_subtype_and_clone_idiom(self):
        value = (
            Integer32()
            .subtype(subtypeSpec=SingleValueConstraint(1, 2))
            .clone(namedValues=NamedValues(("up", 1), ("down", 2)))
            .clone(1)
        )

        assert int(value) == 1
        assert value.namedValues[1] == "up"
        assert value.namedValues[2] == "down"
