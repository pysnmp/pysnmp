"""Unit tests for SMI builder, view, indices, instrumentation, and bundled MIBs."""

import pytest

from pysnmp.smi import builder, view, error, exval, indices
from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity
from pysnmp.proto.rfc1902 import OctetString, Integer, ObjectIdentifier
from pysnmp.entity.engine import SnmpEngine


@pytest.fixture(scope="module")
def mib_builder():
    return SnmpEngine().getMibBuilder()


@pytest.fixture(scope="module")
def mib_view_controller(mib_builder):
    return view.MibViewController(mib_builder)


class TestSmiError:
    def test_smi_error(self):
        err = error.SmiError('test')
        assert 'test' in str(err)

    def test_mib_load_error(self):
        err = error.MibLoadError('test')
        assert isinstance(err, error.SmiError)

    def test_mib_not_found_error(self):
        err = error.MibNotFoundError('test')
        assert isinstance(err, error.MibLoadError)

    def test_mib_operation_error(self):
        err = error.MibOperationError(idx=0)
        assert err['idx'] == 0
        assert 'idx' in err
        assert err.get('idx') == 0

    def test_mib_operation_error_keys(self):
        err = error.MibOperationError(idx=0, oid=(1, 3))
        assert 'idx' in err.keys()

    def test_mib_operation_error_update(self):
        err = error.MibOperationError(idx=0)
        err.update({'oid': (1, 3)})
        assert err['oid'] == (1, 3)

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
        d['a'] = 1
        d['b'] = 2
        assert d['a'] == 1
        assert d['b'] == 2

    def test_keys_ordered(self):
        d = indices.OrderedDict()
        d['b'] = 2
        d['a'] = 1
        d['c'] = 3
        keys = d.keys()
        assert keys == ['a', 'b', 'c']

    def test_values(self):
        d = indices.OrderedDict()
        d['b'] = 2
        d['a'] = 1
        vals = d.values()
        assert vals == [1, 2]

    def test_items(self):
        d = indices.OrderedDict()
        d['b'] = 2
        d['a'] = 1
        items = d.items()
        assert items == [('a', 1), ('b', 2)]

    def test_delete(self):
        d = indices.OrderedDict()
        d['a'] = 1
        d['b'] = 2
        del d['a']
        assert 'a' not in d
        assert d.keys() == ['b']

    def test_clear(self):
        d = indices.OrderedDict()
        d['a'] = 1
        d.clear()
        assert len(d) == 0

    def test_next_key(self):
        d = indices.OrderedDict()
        d['a'] = 1
        d['b'] = 2
        d['c'] = 3
        assert d.nextKey('a') == 'b'
        assert d.nextKey('b') == 'c'

    def test_next_key_not_found(self):
        d = indices.OrderedDict()
        d['a'] = 1
        with pytest.raises(KeyError):
            d.nextKey('a')

    def test_next_key_bisect(self):
        d = indices.OrderedDict()
        d['a'] = 1
        d['c'] = 3
        # 'b' is not in dict, bisect should find 'c'
        assert d.nextKey('b') == 'c'

    def test_update_from_dict(self):
        d = indices.OrderedDict()
        d.update({'a': 1, 'b': 2})
        assert d['a'] == 1
        assert d['b'] == 2

    def test_update_from_iterable(self):
        d = indices.OrderedDict()
        d.update([('a', 1), ('b', 2)])
        assert d['a'] == 1
        assert d['b'] == 2

    def test_update_kwargs(self):
        d = indices.OrderedDict()
        d.update(a=1, b=2)
        assert d['a'] == 1

    def test_get_keys_lens(self):
        d = indices.OrderedDict()
        d['a'] = 1
        d['bb'] = 2
        lens = d.getKeysLens()
        assert sorted(lens) == [1, 2]


class TestOidOrderedDict:
    def test_set_get(self):
        d = indices.OidOrderedDict()
        d[(1, 3, 6)] = 'a'
        d[(1, 3, 7)] = 'b'
        assert d[(1, 3, 6)] == 'a'

    def test_string_key(self):
        d = indices.OidOrderedDict()
        d['1.3.6'] = 'a'
        assert d['1.3.6'] == 'a'

    def test_oid_sorting(self):
        d = indices.OidOrderedDict()
        d[(1, 3, 6, 2)] = 'b'
        d[(1, 3, 6, 1)] = 'a'
        d[(1, 3, 6, 3)] = 'c'
        keys = d.keys()
        assert keys == [(1, 3, 6, 1), (1, 3, 6, 2), (1, 3, 6, 3)]

    def test_delete(self):
        d = indices.OidOrderedDict()
        d[(1, 3, 6)] = 'a'
        del d[(1, 3, 6)]
        assert (1, 3, 6) not in d


class TestMibBuilder:
    def test_load_modules(self, mib_builder):
        mib_builder.loadModules('SNMPv2-MIB')
        assert 'SNMPv2-MIB' in mib_builder.mibSymbols

    def test_import_symbols(self, mib_builder):
        sysDescr = mib_builder.importSymbols('SNMPv2-MIB', 'sysDescr')
        assert sysDescr is not None
        assert sysDescr[0].name == (1, 3, 6, 1, 2, 1, 1, 1)

    def test_import_multiple_symbols(self, mib_builder):
        result = mib_builder.importSymbols('SNMPv2-MIB', 'sysDescr', 'sysObjectID', 'sysUpTime')
        assert len(result) == 3

    def test_load_multiple_modules(self, mib_builder):
        mib_builder.loadModules('SNMP-FRAMEWORK-MIB', 'SNMP-TARGET-MIB')
        assert 'SNMP-FRAMEWORK-MIB' in mib_builder.mibSymbols
        assert 'SNMP-TARGET-MIB' in mib_builder.mibSymbols

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
        oi = ObjectIdentity('1.3.6.1.2.1.1.1.0')
        assert oi is not None

    def test_from_mib_name_and_symbol(self):
        oi = ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)
        assert oi is not None

    def test_get_mib_symbol_unresolved(self):
        oi = ObjectIdentity('1.3.6.1.2.1.1.1.0')
        with pytest.raises(error.SmiError):
            oi.getMibSymbol()

    def test_get_oid_unresolved(self):
        oi = ObjectIdentity('1.3.6.1.2.1.1.1.0')
        with pytest.raises(error.SmiError):
            oi.getOid()

    def test_is_fully_resolved(self):
        oi = ObjectIdentity('1.3.6.1.2.1.1.1.0')
        assert not oi.isFullyResolved()

    def test_resolve_with_mib(self, mib_view_controller):
        oi = ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)
        oi.resolveWithMib(mib_view_controller)
        assert oi.isFullyResolved()
        modName, symName, indices = oi.getMibSymbol()
        assert modName == 'SNMPv2-MIB'
        assert symName == 'sysDescr'

    def test_resolve_oid_to_mib_symbol(self, mib_view_controller):
        oi = ObjectIdentity('1.3.6.1.2.1.1.1.0')
        oi.resolveWithMib(mib_view_controller)
        assert oi.isFullyResolved()
        modName, symName, indices = oi.getMibSymbol()
        assert modName == 'SNMPv2-MIB'
        assert symName == 'sysDescr'

    def test_get_oid_resolved(self, mib_view_controller):
        oi = ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)
        oi.resolveWithMib(mib_view_controller)
        oid = oi.getOid()
        assert tuple(oid) == (1, 3, 6, 1, 2, 1, 1, 1, 0)

    def test_get_label(self, mib_view_controller):
        oi = ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)
        oi.resolveWithMib(mib_view_controller)
        label = oi.getLabel()
        assert 'sysDescr' in label


class TestObjectType:
    def test_creation(self):
        ot = ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'), OctetString('test'))
        assert ot is not None

    def test_resolve_with_mib(self, mib_view_controller):
        ot = ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0), OctetString('test'))
        ot.resolveWithMib(mib_view_controller)
        assert ot.isFullyResolved()

    def test_unresolved_raises(self):
        ot = ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'), OctetString('test'))
        assert not ot.isFullyResolved()

    def test_is_fully_resolved(self):
        ot = ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'), OctetString('test'))
        assert not ot.isFullyResolved()


class TestBundledMibs:
    """Test that each bundled MIB loads through the public MibBuilder."""

    BUNDLED_MIBS = [
        'SNMPv2-MIB',
        'SNMPv2-SMI',
        'SNMPv2-TC',
        'SNMPv2-CONF',
        'SNMPv2-TM',
        'SNMP-FRAMEWORK-MIB',
        'SNMP-MPD-MIB',
        'SNMP-COMMUNITY-MIB',
        'SNMP-TARGET-MIB',
        'SNMP-NOTIFICATION-MIB',
        'SNMP-PROXY-MIB',
        'SNMP-USER-BASED-SM-MIB',
        'SNMP-USER-BASED-SM-3DES-MIB',
        'SNMP-USM-AES-MIB',
        'SNMP-USM-HMAC-SHA2-MIB',
        'SNMP-VIEW-BASED-ACM-MIB',
        'PYSNMP-MIB',
        'PYSNMP-SOURCE-MIB',
        'PYSNMP-USM-MIB',
        'RFC1213-MIB',
        'RFC1158-MIB',
        'INET-ADDRESS-MIB',
        'TRANSPORT-ADDRESS-MIB',
    ]

    def test_load_all_bundled_mibs(self, mib_builder):
        for mib_name in self.BUNDLED_MIBS:
            mib_builder.loadModules(mib_name)
            assert mib_name in mib_builder.mibSymbols, f"Failed to load {mib_name}"

    def test_snmpv2_mib_symbols(self, mib_builder):
        mib_builder.loadModules('SNMPv2-MIB')
        sysDescr, = mib_builder.importSymbols('SNMPv2-MIB', 'sysDescr')
        assert sysDescr.name == (1, 3, 6, 1, 2, 1, 1, 1)

    def test_snmpv2_smi_symbols(self, mib_builder):
        mib_builder.loadModules('SNMPv2-SMI')
        iso, = mib_builder.importSymbols('SNMPv2-SMI', 'iso')
        assert tuple(iso.name) == (1,)

    def test_snmp_framework_mib_symbols(self, mib_builder):
        mib_builder.loadModules('SNMP-FRAMEWORK-MIB')
        snmpEngineID, = mib_builder.importSymbols('SNMP-FRAMEWORK-MIB', 'snmpEngineID')
        assert snmpEngineID is not None

    def test_snmp_target_mib_symbols(self, mib_builder):
        mib_builder.loadModules('SNMP-TARGET-MIB')
        snmpTargetAddrEntry, = mib_builder.importSymbols('SNMP-TARGET-MIB', 'snmpTargetAddrEntry')
        assert snmpTargetAddrEntry is not None

    def test_snmp_view_acm_mib_symbols(self, mib_builder):
        mib_builder.loadModules('SNMP-VIEW-BASED-ACM-MIB')
        vacmContextName, = mib_builder.importSymbols('SNMP-VIEW-BASED-ACM-MIB', 'vacmContextName')
        assert vacmContextName is not None

    def test_rfc1213_mib_symbols(self, mib_builder):
        mib_builder.loadModules('RFC1213-MIB')
        # RFC1213-MIB defines many MIB objects
        assert 'RFC1213-MIB' in mib_builder.mibSymbols
        assert len(mib_builder.mibSymbols['RFC1213-MIB']) > 0

    def test_inet_address_mib_symbols(self, mib_builder):
        mib_builder.loadModules('INET-ADDRESS-MIB')
        InetAddress, = mib_builder.importSymbols('INET-ADDRESS-MIB', 'InetAddress')
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