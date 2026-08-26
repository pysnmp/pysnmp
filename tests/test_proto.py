"""Unit tests for protocol RFC modules and API layer."""

import pytest

from pyasn1.type import univ
from pyasn1.codec.ber import decoder, encoder

from pysnmp.proto import rfc1155, rfc1157, rfc1901, rfc1902, rfc1905, rfc3411
from pysnmp.proto import error as proto_error, errind
from pysnmp.proto.api import verdec, v1, v2c


class TestRfc1902Types:
    def test_integer32_creation(self):
        val = rfc1902.Integer32(42)
        assert int(val) == 42

    def test_integer32_range_constraint(self):
        with pytest.raises(Exception):
            rfc1902.Integer32(2147483648)

    def test_integer_creation(self):
        val = rfc1902.Integer(99)
        assert int(val) == 99

    def test_integer_with_named_values(self):
        State = rfc1902.Integer.withNamedValues(enable=1, disable=0)
        val = State('enable')
        assert int(val) == 1

    def test_integer_with_range(self):
        Small = rfc1902.Integer32.withRange(1, 10)
        assert int(Small(5)) == 5
        with pytest.raises(Exception):
            Small(100)

    def test_integer_with_values(self):
        Discreet = rfc1902.Integer32.withValues(4, 8, 1)
        assert int(Discreet(4)) == 4
        with pytest.raises(Exception):
            Discreet(5)

    def test_octet_string_creation(self):
        val = rfc1902.OctetString('hello')
        assert str(val) == 'hello'

    def test_octet_string_hexvalue(self):
        val = rfc1902.OctetString(hexValue='deadbeef')
        assert val.asOctets() == b'\xde\xad\xbe\xef'

    def test_octet_string_concat(self):
        val = rfc1902.OctetString('hello') + ' world'
        assert str(val) == 'hello world'

    def test_object_identifier(self):
        oid = rfc1902.ObjectIdentifier((1, 3, 6, 1))
        assert tuple(oid) == (1, 3, 6, 1)

    def test_counter32(self):
        val = rfc1902.Counter32(100)
        assert int(val) == 100

    def test_gauge32(self):
        val = rfc1902.Gauge32(200)
        assert int(val) == 200

    def test_unsigned32(self):
        val = rfc1902.Unsigned32(300)
        assert int(val) == 300

    def test_time_ticks(self):
        val = rfc1902.TimeTicks(500)
        assert int(val) == 500

    def test_counter64(self):
        val = rfc1902.Counter64(2**40)
        assert int(val) == 2**40

    def test_ip_address(self):
        val = rfc1902.IpAddress('192.168.1.1')
        assert '192.168.1.1' in val.prettyPrint()

    def test_ip_address_bad(self):
        with pytest.raises(proto_error.ProtocolError):
            rfc1902.IpAddress('not.an.ip')

    def test_null(self):
        val = rfc1902.Null('')
        assert str(val) == ''

    def test_bits(self):
        val = rfc1902.Bits()
        assert val is not None

    def test_opaque(self):
        val = rfc1902.Opaque(b'\x01\x02')
        assert val is not None


class TestRfc1905Pdu:
    def test_get_request_pdu(self):
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        assert int(v2c.apiPDU.getRequestID(pdu)) >= 0

    def test_set_request_pdu(self):
        pdu = rfc1905.SetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        assert int(v2c.apiPDU.getErrorStatus(pdu)) == 0

    def test_response_pdu(self):
        req = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(req)
        rsp = v2c.apiPDU.getResponse(req)
        assert int(v2c.apiPDU.getRequestID(rsp)) == int(v2c.apiPDU.getRequestID(req))

    def test_get_bulk_request_pdu(self):
        pdu = rfc1905.GetBulkRequestPDU()
        v2c.apiBulkPDU.setDefaults(pdu)
        assert int(v2c.apiBulkPDU.getNonRepeaters(pdu)) == 0
        assert int(v2c.apiBulkPDU.getMaxRepetitions(pdu)) == 10

    def test_no_such_object(self):
        assert 'No Such Object' in rfc1905.noSuchObject.prettyPrint()

    def test_no_such_instance(self):
        assert 'No Such Instance' in rfc1905.noSuchInstance.prettyPrint()

    def test_end_of_mib_view(self):
        assert 'No more variables' in rfc1905.endOfMibView.prettyPrint()

    def test_var_bind_set_get(self):
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        varBinds = [((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1902.OctetString('test'))]
        v2c.apiPDU.setVarBinds(pdu, varBinds)
        result = v2c.apiPDU.getVarBinds(pdu)
        assert len(result) == 1
        assert tuple(result[0][0]) == (1, 3, 6, 1, 2, 1, 1, 1, 0)

    def test_error_status_named_values(self):
        assert int(rfc1905.errorStatus.clone('noError')) == 0
        assert int(rfc1905.errorStatus.clone('tooBig')) == 1
        assert int(rfc1905.errorStatus.clone('genErr')) == 5

    def test_pdu_choice(self):
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        msg = rfc1905.PDUs()
        msg.setComponentByType(pdu.tagSet, pdu)
        assert msg is not None

    def test_set_end_of_mib_error(self):
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        varBinds = [((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1902.OctetString('test'))]
        v2c.apiPDU.setVarBinds(pdu, varBinds)
        v2c.apiPDU.setEndOfMibError(pdu, 1)
        # Verify the error was set by checking the var bind list directly
        vbList = v2c.apiPDU.getVarBindList(pdu)
        assert vbList[0][1].tagSet == rfc1905.EndOfMibView.tagSet

    def test_set_no_such_instance_error(self):
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        varBinds = [((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1902.OctetString('test'))]
        v2c.apiPDU.setVarBinds(pdu, varBinds)
        v2c.apiPDU.setNoSuchInstanceError(pdu, 1)
        # Verify the error was set by checking the var bind list directly
        vbList = v2c.apiPDU.getVarBindList(pdu)
        assert vbList[0][1].tagSet == rfc1905.NoSuchInstance.tagSet

    def test_bulk_var_bind_table(self):
        req = rfc1905.GetBulkRequestPDU()
        v2c.apiBulkPDU.setDefaults(req)
        v2c.apiBulkPDU.setNonRepeaters(req, 1)
        v2c.apiBulkPDU.setMaxRepetitions(req, 2)
        reqVarBinds = [
            ((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1902.Null('')),
            ((1, 3, 6, 1, 2, 1, 1, 2, 0), rfc1902.Null('')),
            ((1, 3, 6, 1, 2, 1, 1, 3, 0), rfc1902.Null('')),
        ]
        v2c.apiBulkPDU.setVarBinds(req, reqVarBinds)

        rsp = rfc1905.ResponsePDU()
        v2c.apiPDU.setDefaults(rsp)
        v2c.apiPDU.setRequestID(rsp, v2c.apiBulkPDU.getRequestID(req))
        rspVarBinds = [
            ((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1902.OctetString('a')),
            ((1, 3, 6, 1, 2, 1, 1, 2, 0), rfc1902.OctetString('b')),
            ((1, 3, 6, 1, 2, 1, 1, 3, 0), rfc1902.OctetString('c')),
            ((1, 3, 6, 1, 2, 1, 1, 4, 0), rfc1902.OctetString('d')),
            ((1, 3, 6, 1, 2, 1, 1, 5, 0), rfc1902.OctetString('e')),
        ]
        v2c.apiPDU.setVarBinds(rsp, rspVarBinds)

        table = v2c.apiBulkPDU.getVarBindTable(req, rsp)
        assert len(table) >= 1


class TestRfc1155Types:
    def test_ip_address(self):
        val = rfc1155.IpAddress('10.0.0.1')
        assert '10.0.0.1' in val.prettyPrint()

    def test_ip_address_pretty_out_empty(self):
        val = rfc1155.IpAddress('0.0.0.0')
        assert val.prettyPrint() == '0.0.0.0'

    def test_counter(self):
        val = rfc1155.Counter(42)
        assert int(val) == 42

    def test_network_address_clone(self):
        na = rfc1155.NetworkAddress()
        cloned = na.clone(rfc1155.IpAddress('1.2.3.4'))
        assert cloned is not None

    def test_network_address_clone_from_name(self):
        na = rfc1155.NetworkAddress()
        cloned, remainder = na.cloneFromName((1, 192, 168, 1, 1, 99), False, None, None)
        assert cloned is not None
        assert remainder == (99,)


class TestRfc1157Message:
    def test_message_creation(self):
        msg = rfc1157.Message()
        assert msg is not None

    def test_version_value(self):
        assert int(rfc1157.version.clone('version-1')) == 0

    def test_get_request_pdu_tag(self):
        pdu = rfc1157.GetRequestPDU()
        assert pdu.tagSet == rfc1157.GetRequestPDU.tagSet

    def test_trap_pdu(self):
        pdu = rfc1157.TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        assert v1.apiTrapPDU.getEnterprise(pdu) is not None

    def test_trap_get_set_generic_trap(self):
        pdu = rfc1157.TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        v1.apiTrapPDU.setGenericTrap(pdu, 3)
        assert int(v1.apiTrapPDU.getGenericTrap(pdu)) == 3

    def test_trap_get_set_enterprise(self):
        pdu = rfc1157.TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        v1.apiTrapPDU.setEnterprise(pdu, (1, 2, 3))
        assert tuple(v1.apiTrapPDU.getEnterprise(pdu)) == (1, 2, 3)

    def test_trap_get_set_agent_addr(self):
        pdu = rfc1157.TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        v1.apiTrapPDU.setAgentAddr(pdu, '10.0.0.1')
        assert '10.0.0.1' in v1.apiTrapPDU.getAgentAddr(pdu).prettyPrint()

    def test_trap_get_set_specific_trap(self):
        pdu = rfc1157.TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        v1.apiTrapPDU.setSpecificTrap(pdu, 42)
        assert int(v1.apiTrapPDU.getSpecificTrap(pdu)) == 42

    def test_trap_get_set_time_stamp(self):
        pdu = rfc1157.TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        v1.apiTrapPDU.setTimeStamp(pdu, 12345)
        assert int(v1.apiTrapPDU.getTimeStamp(pdu)) == 12345

    def test_v1_pdu_api_defaults(self):
        pdu = rfc1157.GetRequestPDU()
        v1.apiPDU.setDefaults(pdu)
        assert int(v1.apiPDU.getErrorStatus(pdu)) == 0
        assert int(v1.apiPDU.getErrorIndex(pdu)) == 0

    def test_v1_pdu_api_var_binds(self):
        pdu = rfc1157.GetRequestPDU()
        v1.apiPDU.setDefaults(pdu)
        varBinds = [((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1155.Opaque(b'\x01'))]
        v1.apiPDU.setVarBinds(pdu, varBinds)
        result = v1.apiPDU.getVarBinds(pdu)
        assert len(result) == 1

    def test_v1_pdu_get_response(self):
        req = rfc1157.GetRequestPDU()
        v1.apiPDU.setDefaults(req)
        rsp = v1.apiPDU.getResponse(req)
        assert int(v1.apiPDU.getRequestID(rsp)) == int(v1.apiPDU.getRequestID(req))

    def test_v1_error_index_out_of_range(self):
        pdu = rfc1157.GetRequestPDU()
        v1.apiPDU.setDefaults(pdu)
        varBinds = [((1, 3, 6), rfc1155.Counter(1))]
        v1.apiPDU.setVarBinds(pdu, varBinds)
        v1.apiPDU.setErrorIndex(pdu, 99)
        # muteErrors=True should clamp
        result = v1.apiPDU.getErrorIndex(pdu, muteErrors=True)
        assert int(result) == 1

    def test_v1_error_index_out_of_range_raises(self):
        pdu = rfc1157.GetRequestPDU()
        v1.apiPDU.setDefaults(pdu)
        varBinds = [((1, 3, 6), rfc1155.Counter(1))]
        v1.apiPDU.setVarBinds(pdu, varBinds)
        v1.apiPDU.setErrorIndex(pdu, 99)
        with pytest.raises(proto_error.ProtocolError):
            v1.apiPDU.getErrorIndex(pdu, muteErrors=False)


class TestRfc1901Message:
    def test_version_value(self):
        assert int(rfc1901.version.clone('version-2c')) == 1

    def test_message_creation(self):
        msg = rfc1901.Message()
        assert msg is not None


class TestRfc3411PduClasses:
    def test_read_class_pdus(self):
        assert rfc1905.GetRequestPDU.tagSet in rfc3411.readClassPDUs
        assert rfc1905.GetNextRequestPDU.tagSet in rfc3411.readClassPDUs
        assert rfc1905.GetBulkRequestPDU.tagSet in rfc3411.readClassPDUs

    def test_write_class_pdus(self):
        assert rfc1905.SetRequestPDU.tagSet in rfc3411.writeClassPDUs

    def test_response_class_pdus(self):
        assert rfc1905.ResponsePDU.tagSet in rfc3411.responseClassPDUs
        assert rfc1905.ReportPDU.tagSet in rfc3411.responseClassPDUs

    def test_notification_class_pdus(self):
        assert rfc1905.SNMPv2TrapPDU.tagSet in rfc3411.notificationClassPDUs
        assert rfc1905.InformRequestPDU.tagSet in rfc3411.notificationClassPDUs

    def test_internal_class_pdus(self):
        assert rfc1905.ReportPDU.tagSet in rfc3411.internalClassPDUs

    def test_confirmed_class_pdus(self):
        assert rfc1905.GetRequestPDU.tagSet in rfc3411.confirmedClassPDUs
        assert rfc1905.SetRequestPDU.tagSet in rfc3411.confirmedClassPDUs

    def test_unconfirmed_class_pdus(self):
        assert rfc1905.ResponsePDU.tagSet in rfc3411.unconfirmedClassPDUs
        assert rfc1905.SNMPv2TrapPDU.tagSet in rfc3411.unconfirmedClassPDUs


class TestVerdec:
    def test_decode_message_version_v1(self):
        msg = rfc1157.Message()
        msg.setComponentByPosition(0, rfc1157.version.clone(0))
        msg.setComponentByPosition(1, univ.OctetString('public'))
        pdu = rfc1157.GetRequestPDU()
        v1.apiPDU.setDefaults(pdu)
        pdus = rfc1157.PDUs()
        pdus.setComponentByType(pdu.tagSet, pdu)
        msg.setComponentByPosition(2, pdus)
        encoded = encoder.encode(msg)
        ver = verdec.decodeMessageVersion(encoded)
        assert int(ver) == 0

    def test_decode_message_version_v2c(self):
        msg = rfc1901.Message()
        msg.setComponentByPosition(0, rfc1901.version.clone(1))
        msg.setComponentByPosition(1, univ.OctetString('public'))
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        pdus = rfc1905.PDUs()
        pdus.setComponentByType(pdu.tagSet, pdu)
        msg.setComponentByPosition(2, pdus)
        encoded = encoder.encode(msg)
        ver = verdec.decodeMessageVersion(encoded)
        assert int(ver) == 1

    def test_decode_bad_ber(self):
        with pytest.raises(proto_error.ProtocolError):
            verdec.decodeMessageVersion(b'\x00\x00\x00')


class TestProtoError:
    def test_protocol_error(self):
        err = proto_error.ProtocolError('test error')
        assert 'test error' in str(err)

    def test_status_information(self):
        si = proto_error.StatusInformation(errorIndication='test')
        assert si['errorIndication'] == 'test'
        assert 'errorIndication' in si
        assert si.get('errorIndication') == 'test'
        assert 'test' in str(si)

    def test_cache_expired_error(self):
        err = proto_error.CacheExpiredError()
        assert err is not None

    def test_internal_error(self):
        err = proto_error.InternalError()
        assert err is not None

    def test_message_processing_error(self):
        err = proto_error.MessageProcessingError()
        assert err is not None

    def test_request_timeout(self):
        err = proto_error.RequestTimeout()
        assert err is not None


class TestErrind:
    def test_error_indication_str(self):
        assert str(errind.requestTimedOut) == 'No SNMP response received before timeout'

    def test_error_indication_equality(self):
        assert errind.requestTimedOut == 'requestTimedOut'

    def test_serialization_error(self):
        assert str(errind.serializationError) == 'SNMP message serialization error'

    def test_deserialization_error(self):
        assert str(errind.deserializationError) == 'SNMP message deserialization error'

    def test_unsupported_msg_processing_model(self):
        assert 'Unknown SNMP message processing model' in str(errind.unsupportedMsgProcessingModel)

    def test_unknown_pdu_handler(self):
        assert 'Unhandled PDU type' in str(errind.unknownPDUHandler)

    def test_unsupported_pdu_type(self):
        assert 'Unsupported SNMP PDU type' in str(errind.unsupportedPDUtype)

    def test_request_timed_out(self):
        assert 'No SNMP response' in str(errind.requestTimedOut)

    def test_empty_response(self):
        assert 'Empty SNMP response' in str(errind.emptyResponse)

    def test_non_reportable(self):
        assert 'Report PDU generation' in str(errind.nonReportable)

    def test_data_mismatch(self):
        assert 'mismatched' in str(errind.dataMismatch)

    def test_engine_id_mismatch(self):
        assert errind.engineIDMismatch is not None


class TestProtoCache:
    def test_cache_add_pop(self):
        from pysnmp.proto.cache import Cache
        c = Cache()
        c.add(1, a=1, b=2)
        result = c.pop(1)
        assert result == {'a': 1, 'b': 2}

    def test_cache_pop_missing(self):
        from pysnmp.proto.cache import Cache
        c = Cache()
        assert c.pop(999) is None

    def test_cache_update(self):
        from pysnmp.proto.cache import Cache
        c = Cache()
        c.add(1, a=1)
        c.update(1, b=2)
        result = c.pop(1)
        assert result == {'a': 1, 'b': 2}

    def test_cache_update_missing_raises(self):
        from pysnmp.proto.cache import Cache
        c = Cache()
        with pytest.raises(proto_error.ProtocolError):
            c.update(999, a=1)

    def test_cache_expire(self):
        from pysnmp.proto.cache import Cache
        c = Cache()
        c.add(1, a=1)
        c.add(2, b=2)
        # Expire all entries
        c.expire(lambda idx, params, ctx: True, None)
        assert c.pop(1) is None
        assert c.pop(2) is None

    def test_cache_expire_selective(self):
        from pysnmp.proto.cache import Cache
        c = Cache()
        c.add(1, a=1)
        c.add(2, b=2)
        # Expire only entry 1
        c.expire(lambda idx, params, ctx: idx == 1, None)
        assert c.pop(1) is None
        assert c.pop(2) is not None


class TestV2cMessageAPI:
    def test_message_defaults(self):
        msg = rfc1901.Message()
        v2c.apiMessage.setDefaults(msg)
        assert int(v2c.apiMessage.getVersion(msg)) == 1

    def test_message_get_set_community(self):
        msg = rfc1901.Message()
        v2c.apiMessage.setDefaults(msg)
        v2c.apiMessage.setCommunity(msg, 'public')
        assert str(v2c.apiMessage.getCommunity(msg)) == 'public'

    def test_message_get_set_pdu(self):
        msg = rfc1901.Message()
        v2c.apiMessage.setDefaults(msg)
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        v2c.apiMessage.setPDU(msg, pdu)
        result = v2c.apiMessage.getPDU(msg)
        assert result is not None

    def test_message_get_response(self):
        req = rfc1901.Message()
        v2c.apiMessage.setDefaults(req)
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        v2c.apiMessage.setPDU(req, pdu)
        rsp = v2c.apiMessage.getResponse(req)
        assert rsp is not None


class TestV1MessageAPI:
    def test_message_defaults(self):
        msg = rfc1157.Message()
        v1.apiMessage.setDefaults(msg)
        assert int(v1.apiMessage.getVersion(msg)) == 0

    def test_message_get_set_community(self):
        msg = rfc1157.Message()
        v1.apiMessage.setDefaults(msg)
        v1.apiMessage.setCommunity(msg, 'public')
        assert str(v1.apiMessage.getCommunity(msg)) == 'public'


class TestProxyRfc2576:
    def test_v1_to_v2_get_request(self):
        pdu = rfc1157.GetRequestPDU()
        v1.apiPDU.setDefaults(pdu)
        v1.apiPDU.setVarBinds(pdu, [((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1155.Counter(42))])
        from pysnmp.proto.proxy import rfc2576
        v2pdu = rfc2576.v1ToV2(pdu)
        assert v2pdu.tagSet == rfc1905.GetRequestPDU.tagSet

    def test_v1_to_v2_trap(self):
        pdu = rfc1157.TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        v1.apiTrapPDU.setGenericTrap(pdu, 0)  # coldStart
        from pysnmp.proto.proxy import rfc2576
        v2pdu = rfc2576.v1ToV2(pdu)
        assert v2pdu.tagSet == rfc1905.SNMPv2TrapPDU.tagSet

    def test_v2_to_v1_get_request(self):
        pdu = rfc1905.GetRequestPDU()
        v2c.apiPDU.setDefaults(pdu)
        v2c.apiPDU.setVarBinds(pdu, [((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1902.Integer(42))])
        from pysnmp.proto.proxy import rfc2576
        v1pdu = rfc2576.v2ToV1(pdu)
        assert v1pdu.tagSet == rfc1157.GetRequestPDU.tagSet

    def test_v2_to_v1_response(self):
        pdu = rfc1905.ResponsePDU()
        v2c.apiPDU.setDefaults(pdu)
        v2c.apiPDU.setVarBinds(pdu, [((1, 3, 6, 1, 2, 1, 1, 1, 0), rfc1902.OctetString('test'))])
        from pysnmp.proto.proxy import rfc2576
        v1pdu = rfc2576.v2ToV1(pdu)
        assert v1pdu.tagSet == rfc1157.GetResponsePDU.tagSet

    def test_v2_to_v1_bulk_becomes_next(self):
        pdu = rfc1905.GetBulkRequestPDU()
        v2c.apiBulkPDU.setDefaults(pdu)
        from pysnmp.proto.proxy import rfc2576
        v1pdu = rfc2576.v2ToV1(pdu)
        assert v1pdu.tagSet == rfc1157.GetNextRequestPDU.tagSet

    def test_v2_to_v1_unsupported_pdu_raises(self):
        pdu = rfc1905.ReportPDU()
        v2c.apiPDU.setDefaults(pdu)
        from pysnmp.proto.proxy import rfc2576
        with pytest.raises(proto_error.ProtocolError):
            rfc2576.v2ToV1(pdu)