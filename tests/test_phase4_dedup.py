"""Characterization tests for the Phase 4 deduplication helpers."""

import time
from types import SimpleNamespace

import pytest
from pyasn1.error import PyAsn1Error
from pyasn1.type import univ

# Importing the engine initializes security modules before entity configuration;
# reversing these imports exposes a legacy circular dependency.
# isort: off
from pysnmp.entity.engine import SnmpEngine
from pysnmp.entity import config, observer

# isort: on
from pysnmp.hlapi.asyncio._callback import make_callback
from pysnmp.proto import errind, error
from pysnmp.proto.api import v2c
from pysnmp.proto.mpmod.rfc3412 import SnmpV3MessageProcessingModel
from pysnmp.proto.rfc3412 import MsgAndPduDispatcher
from pysnmp.proto.secmod.rfc3414.service import _raise_usm_error, _run_or_raise_serialization_error


class _Future:
    def __init__(self, cancelled=False):
        self._cancelled = cancelled
        self.result = None
        self.exception = None

    def cancelled(self):
        return self._cancelled

    def set_result(self, result):
        self.result = result

    def set_exception(self, exception):
        self.exception = exception


def test_execution_context_preserves_writable_mapping():
    meta_observer = observer.MetaObserver()
    engine = SimpleNamespace(observer=meta_observer)
    variables = {"communityName": "public"}

    def rewrite_community(snmpEngine, execpoint, context, cbCtx):
        context["communityName"] = "private"

    meta_observer.registerObserver(rewrite_community, "test.writable")

    with observer.execution_context(engine, "test.writable", variables) as context:
        assert context is variables
        assert meta_observer.getExecutionContext("test.writable") is variables

    assert variables["communityName"] == "private"
    with pytest.raises(KeyError):
        meta_observer.getExecutionContext("test.writable")


def test_execution_context_clears_after_body_exception():
    meta_observer = observer.MetaObserver()
    engine = SimpleNamespace(observer=meta_observer)

    with pytest.raises(RuntimeError, match="boom"):
        with observer.execution_context(engine, "test.exception", value=1):
            assert meta_observer.getExecutionContext("test.exception") == {"value": 1}
            raise RuntimeError("boom")

    with pytest.raises(KeyError):
        meta_observer.getExecutionContext("test.exception")


def test_execution_context_restores_outer_context():
    meta_observer = observer.MetaObserver()
    engine = SimpleNamespace(observer=meta_observer)
    outer = {"level": "outer"}
    inner = {"level": "inner"}

    with observer.execution_context(engine, "test.nested", outer):
        with observer.execution_context(engine, "test.nested", inner):
            assert meta_observer.getExecutionContext("test.nested") is inner

        assert meta_observer.getExecutionContext("test.nested") is outer

    with pytest.raises(KeyError):
        meta_observer.getExecutionContext("test.nested")


def test_execution_context_clears_when_observer_raises():
    meta_observer = observer.MetaObserver()
    engine = SimpleNamespace(observer=meta_observer)

    def fail_observer(snmpEngine, execpoint, context, cbCtx):
        raise RuntimeError("observer failure")

    meta_observer.registerObserver(fail_observer, "test.observer-error")

    with pytest.raises(RuntimeError, match="observer failure"):
        with observer.execution_context(engine, "test.observer-error"):
            pass

    with pytest.raises(KeyError):
        meta_observer.getExecutionContext("test.observer-error")


def test_execution_context_rejects_mapping_and_keywords():
    engine = SimpleNamespace(observer=observer.MetaObserver())

    with pytest.raises(TypeError, match="either a mapping or keyword variables"):
        with observer.execution_context(engine, "test.invalid", {}, value=1):
            pass


def test_callback_unmakes_flat_varbinds():
    future = _Future()
    callback = make_callback(lambda engine, varBinds, lookupMib: tuple(varBinds))

    callback(None, None, None, 0, 0, [1, 2], (True, future))

    assert future.result == (None, 0, 0, (1, 2))
    assert future.exception is None


def test_callback_unmakes_each_table_row():
    future = _Future()
    callback = make_callback(lambda engine, varBinds, lookupMib: tuple(varBinds), multi_row=True)

    callback(None, None, None, 0, 0, [[1], [2]], (True, future))

    assert future.result == (None, 0, 0, [(1,), (2,)])


def test_callback_propagates_unmake_exception_to_future():
    failure = ValueError("bad varbind")
    future = _Future()

    def fail(engine, varBinds, lookupMib):
        raise failure

    callback = make_callback(fail)
    callback(None, None, None, 0, 0, [], (True, future))

    assert future.exception is failure
    assert future.result is None


def test_callback_ignores_cancelled_future():
    future = _Future(cancelled=True)

    def fail_if_called(engine, varBinds, lookupMib):
        pytest.fail("cancelled callback should not process varbinds")

    callback = make_callback(fail_if_called)
    callback(None, None, None, 0, 0, [], (True, future))

    assert future.result is None
    assert future.exception is None


def test_usm_error_helper_preserves_exact_key_set():
    with pytest.raises(error.StatusInformation) as exc_info:
        _raise_usm_error(errind.unknownEngineID, oid="counter", val=1)

    status = exc_info.value
    assert status["errorIndication"] is errind.unknownEngineID
    assert status["oid"] == "counter"
    assert status["val"] == 1
    assert "msgUserName" not in status
    assert "securityStateReference" not in status


def test_serialization_helper_covers_component_assignment():
    def fail_assignment():
        raise PyAsn1Error("component assignment failed")

    with pytest.raises(error.StatusInformation) as exc_info:
        _run_or_raise_serialization_error(fail_assignment, "securityParameters")

    assert exc_info.value["errorIndication"] is errind.serializationError


class _HeaderRecorder:
    def __init__(self):
        self.calls = []

    def setComponentByPosition(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self


class _MessageRecorder:
    def __init__(self, header):
        self.header = header

    def setComponentByPosition(self, *args, **kwargs):
        return self

    def getComponentByPosition(self, position):
        assert position == 1
        return self.header


class _SecurityModelValue:
    def __init__(self):
        self.int_calls = 0

    def __int__(self):
        self.int_calls += 1
        return 3


def _record_header_assembly(response):
    header = _HeaderRecorder()
    model = SnmpV3MessageProcessingModel()
    model._snmpMsgSpec = _MessageRecorder(header)
    max_message_size = SimpleNamespace(syntax=65507)
    mib_builder = SimpleNamespace(importSymbols=lambda *args: (max_message_size,))
    engine = SimpleNamespace(
        msgAndPduDsp=SimpleNamespace(mibInstrumController=SimpleNamespace(mibBuilder=mib_builder))
    )
    security_model = _SecurityModelValue()
    pdu = SimpleNamespace(tagSet=univ.Null().tagSet)

    model._assemble_msg_header(engine, 1, 1, security_model, pdu, response=response)

    return header.calls[-1], security_model


def test_outgoing_header_preserves_security_model_coercion():
    call, security_model = _record_header_assembly(response=False)

    assert call == ((3, 3), {})
    assert security_model.int_calls == 1


def test_response_header_preserves_uncoerced_security_model_and_options():
    call, security_model = _record_header_assembly(response=True)

    assert call == (
        (3, security_model),
        {
            "verifyConstraints": False,
            "matchTags": False,
            "matchConstraints": False,
        },
    )
    assert security_model.int_calls == 0


class _RecordingTransportDispatcher:
    def __init__(self):
        self.messages = []

    def sendMessage(self, *args):
        self.messages.append(args)

    def getTimerResolution(self):
        return 1.0


def _build_v3_request(
    *,
    security_level,
    sender_user="test-user",
    receiver_user="test-user",
    sender_auth_key="authkey1",
    receiver_auth_key="authkey1",
    sender_priv_key="privkey1",
    receiver_priv_key="privkey1",
    synchronize_time=True,
):
    sender = SnmpEngine(snmpEngineID=univ.OctetString(hexValue="80004fb8050102030405"))
    receiver = SnmpEngine(snmpEngineID=univ.OctetString(hexValue="80004fb805060708090a"))
    receiver.transportDispatcher = _RecordingTransportDispatcher()

    auth_protocol = (
        config.usmHMACMD5AuthProtocol if security_level >= 2 else config.usmNoAuthProtocol
    )
    priv_protocol = config.usmDESPrivProtocol if security_level == 3 else config.usmNoPrivProtocol
    config.addV3User(
        sender,
        sender_user,
        authProtocol=auth_protocol,
        authKey=sender_auth_key if security_level >= 2 else None,
        privProtocol=priv_protocol,
        privKey=sender_priv_key if security_level == 3 else None,
        securityEngineId=receiver.snmpEngineID,
    )
    config.addV3User(
        receiver,
        receiver_user,
        authProtocol=auth_protocol,
        authKey=receiver_auth_key if security_level >= 2 else None,
        privProtocol=priv_protocol,
        privKey=receiver_priv_key if security_level == 3 else None,
    )

    if security_level >= 2 and synchronize_time:
        engine_boots, engine_time = (
            receiver.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                "__SNMP-FRAMEWORK-MIB", "snmpEngineBoots", "snmpEngineTime"
            )
        )
        current_engine_time = engine_time.syntax.clone()
        sender.securityModels[3]._SnmpUSMSecurityModel__timeline[receiver.snmpEngineID] = (
            engine_boots.syntax,
            current_engine_time,
            current_engine_time,
            int(time.time()),
        )

    pdu = v2c.GetRequestPDU()
    v2c.apiPDU.setDefaults(pdu)
    v2c.apiPDU.setVarBinds(pdu, [((1, 3, 6, 1, 2, 1, 1, 1, 0), univ.Null(""))])
    transport_domain = (1, 3, 6, 1, 6, 1, 1)
    transport_address = ("127.0.0.1", 161)
    message_model = sender.messageProcessingSubsystems[3]
    message_model._SnmpV3MessageProcessingModel__engineIdCache[
        (transport_domain, transport_address)
    ] = {
        "securityEngineId": receiver.snmpEngineID,
        "contextEngineId": receiver.snmpEngineID,
        "contextName": univ.OctetString(""),
    }
    whole_message = message_model.prepareOutgoingMessage(
        sender,
        transport_domain,
        transport_address,
        3,
        3,
        univ.OctetString(sender_user),
        security_level,
        receiver.snmpEngineID,
        "",
        1,
        pdu,
        True,
        1,
    )[2]

    return receiver, transport_domain, transport_address, whole_message


def _prepare_v3_request(receiver, transport_domain, transport_address, whole_message):
    return receiver.messageProcessingSubsystems[3].prepareDataElements(
        receiver, transport_domain, transport_address, whole_message
    )


def test_prepare_data_elements_characterizes_unknown_user():
    request = _build_v3_request(
        security_level=1,
        sender_user="missing-user",
        receiver_user="other-user",
    )

    with pytest.raises(error.StatusInformation) as exc_info:
        _prepare_v3_request(*request)

    status = exc_info.value
    assert status["errorIndication"] is errind.unknownSecurityName
    assert status["msgUserName"] == univ.OctetString("missing-user")
    assert "securityStateReference" in status
    assert "oid" in status


def test_prepare_data_elements_characterizes_wrong_digest():
    request = _build_v3_request(security_level=2, receiver_auth_key="wrongkey1")

    with pytest.raises(error.StatusInformation) as exc_info:
        _prepare_v3_request(*request)

    status = exc_info.value
    assert status["errorIndication"] is errind.authenticationFailure
    assert status["msgUserName"] == univ.OctetString("test-user")
    assert "securityStateReference" in status
    assert "oid" in status


def test_prepare_data_elements_characterizes_not_in_time_window():
    request = _build_v3_request(security_level=2, synchronize_time=False)

    with pytest.raises(error.StatusInformation) as exc_info:
        _prepare_v3_request(*request)

    status = exc_info.value
    assert status["errorIndication"] is errind.notInTimeWindow
    assert status["securityLevel"] == 2
    assert status["msgUserName"] == univ.OctetString("test-user")
    assert "oid" in status


def test_prepare_data_elements_characterizes_decryption_error():
    request = _build_v3_request(security_level=3, receiver_priv_key="wrongkey1")

    with pytest.raises(error.StatusInformation) as exc_info:
        _prepare_v3_request(*request)

    status = exc_info.value
    assert status["errorIndication"] is errind.decryptionError
    assert status["msgUserName"] == univ.OctetString("test-user")


def test_request_transport_context_is_removed_when_application_raises(monkeypatch):
    dispatcher = MsgAndPduDispatcher()
    context_engine_id = univ.OctetString("engine")
    pdu = v2c.GetRequestPDU()
    v2c.apiPDU.setDefaults(pdu)
    state_reference = 17

    class MessageModel:
        def prepareDataElements(self, *args):
            return (
                3,
                3,
                univ.OctetString("user"),
                1,
                context_engine_id,
                univ.OctetString(""),
                1,
                pdu,
                pdu.tagSet,
                None,
                65507,
                None,
                state_reference,
            )

    def fail_processing(*args):
        raise RuntimeError("application failure")

    dispatcher.registerContextEngineId(context_engine_id, (pdu.tagSet,), fail_processing)
    engine = SimpleNamespace(
        messageProcessingSubsystems={3: MessageModel()},
        observer=observer.MetaObserver(),
    )
    monkeypatch.setattr("pysnmp.proto.rfc3412.verdec.decodeMessageVersion", lambda msg: 3)

    with pytest.raises(RuntimeError, match="application failure"):
        dispatcher.receiveMessage(engine, "domain", "address", b"message")

    with pytest.raises(error.ProtocolError):
        dispatcher.getTransportInfo(state_reference)
    with pytest.raises(KeyError):
        engine.observer.getExecutionContext("rfc3412.receiveMessage:request")
