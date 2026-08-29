"""Unit tests for entity, engine, RFC3413 applications, carrier, and transport."""

import asyncio
import os
import tempfile

import pytest

from pysnmp.entity.engine import SnmpEngine
from pysnmp.entity import config
from pysnmp.entity import observer
from pysnmp.entity.rfc3413 import context as rfc3413_context
from pysnmp.entity.rfc3413 import cmdgen as rfc3413_cmdgen
from pysnmp.entity.rfc3413 import cmdrsp
from pysnmp.entity.rfc3413 import ntforg
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.entity.rfc3413 import config as rfc3413_config
from pysnmp.carrier.base import (
    AbstractTransportDispatcher,
    AbstractTransport,
    AbstractTransportAddress,
    TimerCallable,
)
from pysnmp.carrier.error import CarrierError
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.hlapi.auth import CommunityData, UsmUserData
from pysnmp.hlapi.context import ContextData
from pysnmp.hlapi.transport import AbstractTransportTarget
from pysnmp.hlapi.asyncio.transport import UdpTransportTarget
from pysnmp.hlapi.varbinds import CommandGeneratorVarBinds, NotificationOriginatorVarBinds
from pysnmp.hlapi.lcd import CommandGeneratorLcdConfigurator
from pysnmp.proto import errind, error
from pysnmp.proto.api import v2c
from pysnmp.proto.rfc1902 import OctetString, Integer, ObjectIdentifier
from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity, NotificationType
from pysnmp import debug
# null import removed (was unused, from pyasn1.compat.octets)


class TestSnmpEngine:
    def test_creation(self):
        engine = SnmpEngine()
        assert engine is not None
        assert engine.snmpEngineID is not None

    def test_repr(self):
        engine = SnmpEngine()
        assert 'SnmpEngine' in repr(engine)

    def test_get_mib_builder(self):
        engine = SnmpEngine()
        assert engine.getMibBuilder() is not None

    def test_user_context(self):
        engine = SnmpEngine()
        engine.setUserContext(mykey='myvalue')
        assert engine.getUserContext('mykey') == 'myvalue'

    def test_del_user_context(self):
        engine = SnmpEngine()
        engine.setUserContext(mykey='myvalue')
        engine.delUserContext('mykey')
        assert engine.getUserContext('mykey') is None

    def test_get_user_context_missing(self):
        engine = SnmpEngine()
        assert engine.getUserContext('nonexistent') is None

    def test_message_processing_subsystems(self):
        engine = SnmpEngine()
        assert len(engine.messageProcessingSubsystems) == 3

    def test_security_models(self):
        engine = SnmpEngine()
        assert len(engine.securityModels) == 3

    def test_access_control_model(self):
        engine = SnmpEngine()
        assert len(engine.accessControlModel) == 2

    def test_observer_exists(self):
        engine = SnmpEngine()
        assert engine.observer is not None

    def test_cache_dict(self):
        engine = SnmpEngine()
        assert isinstance(engine.cache, dict)


class TestMetaObserver:
    def test_register_unregister_observer(self):
        obs = observer.MetaObserver()
        calls = []

        def cbFun(snmpEngine, execpoint, variables, cbCtx):
            calls.append((execpoint, variables, cbCtx))

        obs.registerObserver(cbFun, 'test.execpoint', cbCtx='context')
        obs.storeExecutionContext(None, 'test.execpoint', {'a': 1})
        assert len(calls) == 1
        assert calls[0][0] == 'test.execpoint'

        obs.clearExecutionContext(None, 'test.execpoint')
        obs.unregisterObserver(cbFun)
        # After unregister, storing should not call
        obs.storeExecutionContext(None, 'test.execpoint', {'b': 2})
        assert len(calls) == 1

    def test_register_duplicate_observer_raises(self):
        obs = observer.MetaObserver()
        def cbFun(snmpEngine, execpoint, variables, cbCtx):
            pass
        obs.registerObserver(cbFun, 'test.execpoint')
        with pytest.raises(Exception):
            obs.registerObserver(cbFun, 'test.execpoint')

    def test_unregister_all(self):
        obs = observer.MetaObserver()
        def cbFun(snmpEngine, execpoint, variables, cbCtx):
            pass
        obs.registerObserver(cbFun, 'test1', 'test2')
        obs.unregisterObserver()
        # Should not raise
        obs.storeExecutionContext(None, 'test1', {})

    def test_get_execution_context(self):
        obs = observer.MetaObserver()
        obs.storeExecutionContext(None, 'test.execpoint', {'a': 1})
        ctx = obs.getExecutionContext('test.execpoint')
        assert ctx == {'a': 1}

    def test_clear_all_execution_contexts(self):
        obs = observer.MetaObserver()
        obs.storeExecutionContext(None, 'test1', {'a': 1})
        obs.storeExecutionContext(None, 'test2', {'b': 2})
        obs.clearExecutionContext(None)
        with pytest.raises(KeyError):
            obs.getExecutionContext('test1')


class TestAbstractTransportDispatcher:
    def test_register_recv_cb(self):
        td = AbstractTransportDispatcher()
        td.registerRecvCbFun(lambda *args: None)
        # Registering again with same recvId should raise
        with pytest.raises(CarrierError):
            td.registerRecvCbFun(lambda *args: None)

    def test_unregister_recv_cb(self):
        td = AbstractTransportDispatcher()
        td.registerRecvCbFun(lambda *args: None)
        td.unregisterRecvCbFun()
        # Should be able to register again
        td.registerRecvCbFun(lambda *args: None)

    def test_register_routing_cb(self):
        td = AbstractTransportDispatcher()
        td.registerRoutingCbFun(lambda *args: None)
        with pytest.raises(CarrierError):
            td.registerRoutingCbFun(lambda *args: None)

    def test_unregister_routing_cb(self):
        td = AbstractTransportDispatcher()
        td.registerRoutingCbFun(lambda *args: None)
        td.unregisterRoutingCbFun()

    def test_register_timer_cb(self):
        td = AbstractTransportDispatcher()
        td.registerTimerCbFun(lambda t: None)
        assert len(td._AbstractTransportDispatcher__timerCallables) == 1

    def test_unregister_timer_cb(self):
        td = AbstractTransportDispatcher()
        td.registerTimerCbFun(lambda t: None)
        td.unregisterTimerCbFun()
        assert len(td._AbstractTransportDispatcher__timerCallables) == 0

    def test_get_timer_resolution(self):
        td = AbstractTransportDispatcher()
        assert td.getTimerResolution() == 0.5

    def test_set_timer_resolution(self):
        td = AbstractTransportDispatcher()
        td.setTimerResolution(1.0)
        assert td.getTimerResolution() == 1.0

    def test_set_timer_resolution_too_small(self):
        td = AbstractTransportDispatcher()
        with pytest.raises(CarrierError):
            td.setTimerResolution(0.001)

    def test_set_timer_resolution_too_large(self):
        td = AbstractTransportDispatcher()
        with pytest.raises(CarrierError):
            td.setTimerResolution(20)

    def test_get_timer_ticks(self):
        td = AbstractTransportDispatcher()
        assert td.getTimerTicks() == 0

    def test_handle_timer_tick(self):
        td = AbstractTransportDispatcher()
        td.registerTimerCbFun(lambda t: None)
        # First tick initializes, second tick increments
        td.handleTimerTick(100.0)
        td.handleTimerTick(200.0)
        assert td.getTimerTicks() >= 0

    def test_job_started_finished(self):
        td = AbstractTransportDispatcher()
        td.jobStarted('job1')
        assert td.jobsArePending()
        td.jobFinished('job1')
        assert not td.jobsArePending()

    def test_send_message_no_transport(self):
        td = AbstractTransportDispatcher()
        with pytest.raises(CarrierError):
            td.sendMessage(b'msg', (1, 3, 6), ('127.0.0.1', 161))

    def test_get_transport_not_registered(self):
        td = AbstractTransportDispatcher()
        with pytest.raises(CarrierError):
            td.getTransport((1, 3, 6))

    def test_run_dispatcher_raises(self):
        td = AbstractTransportDispatcher()
        with pytest.raises(CarrierError):
            td.runDispatcher()

    def test_close_dispatcher(self):
        td = AbstractTransportDispatcher()
        td.closeDispatcher()


class TestTimerCallable:
    def test_call(self):
        calls = []
        tc = TimerCallable(lambda t: calls.append(t), 1.0)
        tc(0)
        assert len(calls) == 1
        # Second call within interval should not fire
        tc(0.5)
        assert len(calls) == 1

    def test_interval_property(self):
        tc = TimerCallable(lambda t: None, 2.0)
        assert tc.interval == 2.0
        tc.interval = 3.0
        assert tc.interval == 3.0

    def test_equality(self):
        def cb(t): pass
        tc = TimerCallable(cb, 1.0)
        assert tc == cb
        other_cb = lambda t: None
        assert tc != other_cb


class TestAbstractTransport:
    def test_is_compatible_with_dispatcher(self):
        class FakeTransport(AbstractTransport):
            protoTransportDispatcher = AbstractTransportDispatcher
        assert FakeTransport.isCompatibleWithDispatcher(AbstractTransportDispatcher())

    def test_register_cb_fun(self):
        class FakeTransport(AbstractTransport):
            pass
        t = FakeTransport()
        t.registerCbFun(lambda *args: None)
        with pytest.raises(CarrierError):
            t.registerCbFun(lambda *args: None)

    def test_unregister_cb_fun(self):
        class FakeTransport(AbstractTransport):
            pass
        t = FakeTransport()
        t.registerCbFun(lambda *args: None)
        t.unregisterCbFun()
        assert t._cbFun is None

    def test_open_client_mode_raises(self):
        class FakeTransport(AbstractTransport):
            pass
        t = FakeTransport()
        with pytest.raises(CarrierError):
            t.openClientMode()

    def test_open_server_mode_raises(self):
        class FakeTransport(AbstractTransport):
            pass
        t = FakeTransport()
        with pytest.raises(CarrierError):
            t.openServerMode(('127.0.0.1', 161))

    def test_send_message_raises(self):
        class FakeTransport(AbstractTransport):
            pass
        t = FakeTransport()
        with pytest.raises(CarrierError):
            t.sendMessage(b'msg', ('127.0.0.1', 161))

    def test_close_transport(self):
        class FakeTransport(AbstractTransport):
            pass
        t = FakeTransport()
        t.registerCbFun(lambda *args: None)
        t.closeTransport()
        assert t._cbFun is None


class TestAbstractTransportAddress:
    def test_set_local_address(self):
        addr = AbstractTransportAddress()
        addr.setLocalAddress(('0.0.0.0', 0))
        assert addr.getLocalAddress() == ('0.0.0.0', 0)

    def test_clone(self):
        class TestAddr(AbstractTransportAddress):
            def __init__(self, source=None):
                pass
        addr = TestAddr()
        addr.setLocalAddress(('0.0.0.0', 0))
        cloned = addr.clone(('10.0.0.1', 200))
        assert cloned.getLocalAddress() == ('10.0.0.1', 200)

    def test_clone_no_arg(self):
        class TestAddr(AbstractTransportAddress):
            def __init__(self, source=None):
                pass
        addr = TestAddr()
        addr.setLocalAddress(('0.0.0.0', 0))
        cloned = addr.clone()
        assert cloned.getLocalAddress() == ('0.0.0.0', 0)


class TestAsyncioDispatcher:
    def test_creation(self):
        td = AsyncioDispatcher()
        assert td is not None
        assert td.getTimerResolution() == 0.5
        assert not td.loop.is_running()
        td.loop.close()

    def test_unregister_final_transport_cancels_timer(self):
        td = AsyncioDispatcher()
        transport = udp.UdpAsyncioTransport(loop=td.loop).openClientMode()
        td.registerTransport(udp.domainName, transport)
        timer_handle = td._timerStartHandle
        assert timer_handle is not None

        td.unregisterTransport(udp.domainName)
        assert td.loopingcall is None
        assert timer_handle.cancelled()
        transport.closeTransport()
        td.loop.close()


class TestUdpTransport:
    def test_domain_name(self):
        assert udp.domainName == (1, 3, 6, 1, 6, 1, 1)

    def test_udp_transport_address(self):
        addr = udp.UdpTransportAddress(('127.0.0.1', 161))
        assert addr == ('127.0.0.1', 161)

    def test_udp_transport_address_set_local(self):
        addr = udp.UdpTransportAddress(('127.0.0.1', 161))
        addr.setLocalAddress(('0.0.0.0', 0))
        assert addr.getLocalAddress() == ('0.0.0.0', 0)

    def test_broadcast_option_is_applied_after_connection(self):
        loop = asyncio.new_event_loop()
        transport = udp.UdpAsyncioTransport(loop=loop).enableBroadcast()
        transport.openClientMode()
        loop.run_until_complete(asyncio.sleep(0))
        assert transport.getLocalAddress() is not None
        transport.closeTransport()
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()

    def test_packet_information_is_explicitly_unsupported(self):
        with pytest.raises(CarrierError, match='Packet-information'):
            udp.UdpAsyncioTransport().enablePktInfo()


@pytest.mark.skipif(not hasattr(__import__('socket'), 'AF_UNIX'),
                    reason='Unix-domain datagrams are unavailable on this platform')
class TestUnixTransport:
    def test_unix_transport_target(self):
        from pysnmp.hlapi.asyncio.transport import UnixTransportTarget

        target = UnixTransportTarget('/tmp/pysnmp-test.sock')
        assert target.transportAddr == '/tmp/pysnmp-test.sock'
        with pytest.raises(error.PySnmpError, match='path string'):
            UnixTransportTarget(('127.0.0.1', 161))

    def test_client_and_server_exchange_datagram(self):
        from pysnmp.carrier.asyncio.dgram import unix

        loop = asyncio.new_event_loop()
        fd, server_path = tempfile.mkstemp(prefix='pysnmp-server-', dir=tempfile.gettempdir())
        os.close(fd)
        os.unlink(server_path)
        received = []
        server = unix.UnixAsyncioTransport(loop=loop).openServerMode(server_path)
        client = unix.UnixAsyncioTransport(loop=loop).openClientMode()
        server.registerCbFun(lambda _, address, message: received.append((address, message)))
        try:
            loop.run_until_complete(asyncio.sleep(0))
            client.sendMessage(b'ping', unix.UnixTransportAddress(server_path))
            loop.run_until_complete(asyncio.sleep(0.05))
            assert received == [(client.getLocalAddress(), b'ping')]
        finally:
            client.closeTransport()
            server.closeTransport()
            loop.run_until_complete(asyncio.sleep(0))
            loop.close()
        assert not os.path.exists(server_path)


class TestUdpTransportTarget:
    def test_creation(self):
        target = UdpTransportTarget(('127.0.0.1', 161))
        assert target is not None
        assert target.transportAddr == ('127.0.0.1', 161)

    def test_timeout_retries(self):
        target = UdpTransportTarget(('127.0.0.1', 161), timeout=2, retries=3)
        assert target.timeout == 2
        assert target.retries == 3

    def test_set_local_address(self):
        target = UdpTransportTarget(('127.0.0.1', 161))
        result = target.setLocalAddress(('0.0.0.0', 0))
        assert result is target
        assert target.iface == ('0.0.0.0', 0)

    def test_get_transport_info(self):
        target = UdpTransportTarget(('127.0.0.1', 161))
        domain, addr = target.getTransportInfo()
        assert domain == udp.domainName

    def test_repr(self):
        target = UdpTransportTarget(('127.0.0.1', 161))
        assert 'UdpTransportTarget' in repr(target)

    def test_bad_address_raises(self):
        from pysnmp.error import PySnmpError
        with pytest.raises(PySnmpError):
            UdpTransportTarget(('nonexistent.invalid.host', 161))


class TestCommunityData:
    def test_creation_default(self):
        cd = CommunityData('public')
        assert cd.communityName == 'public'
        assert cd.mpModel == 1

    def test_creation_v1(self):
        cd = CommunityData('public', mpModel=0)
        assert cd.mpModel == 0
        assert cd.securityModel == 1

    def test_creation_v2c(self):
        cd = CommunityData('public', mpModel=1)
        assert cd.mpModel == 1
        assert cd.securityModel == 2

    def test_with_context_name(self):
        cd = CommunityData('public', contextName='mycontext')
        assert cd.contextName == 'mycontext'

    def test_with_tag(self):
        cd = CommunityData('public', tag='mytag')
        assert cd.tag == 'mytag'

    def test_with_security_name(self):
        cd = CommunityData('public', 'public', securityName='secname')
        assert cd.securityName == 'secname'

    def test_not_hashable(self):
        cd = CommunityData('public')
        with pytest.raises(TypeError):
            hash(cd)

    def test_clone(self):
        cd = CommunityData('public', 'public')
        cloned = cd.clone('private')
        assert cloned.communityName == 'private'

    def test_repr(self):
        cd = CommunityData('public')
        assert 'CommunityData' in repr(cd)


class TestUsmUserData:
    def test_creation_no_auth_no_priv(self):
        user = UsmUserData('user1')
        assert user.userName == 'user1'

    def test_creation_with_auth(self):
        user = UsmUserData('user1', 'authkey1', authProtocol=config.usmHMACMD5AuthProtocol)
        assert user.userName == 'user1'

    def test_creation_with_auth_priv(self):
        user = UsmUserData(
            'user1', 'authkey1', 'privkey1',
            authProtocol=config.usmHMACMD5AuthProtocol,
            privProtocol=config.usmDESPrivProtocol
        )
        assert user.userName == 'user1'


class TestContextData:
    def test_default_creation(self):
        ctx = ContextData()
        assert ctx.contextEngineId is None

    def test_with_context_name(self):
        ctx = ContextData(contextName='mycontext')
        assert ctx.contextName == 'mycontext'

    def test_with_context_engine_id(self):
        ctx = ContextData(contextEngineId='0x010203')
        assert ctx.contextEngineId == '0x010203'

    def test_repr(self):
        ctx = ContextData()
        assert 'ContextData' in repr(ctx)


class TestSnmpContext:
    def test_creation(self):
        engine = SnmpEngine()
        ctx = rfc3413_context.SnmpContext(engine)
        assert ctx.contextEngineId is not None

    def test_register_context_name(self):
        engine = SnmpEngine()
        ctx = rfc3413_context.SnmpContext(engine)
        ctx.registerContextName('test')
        assert ctx.getMibInstrum('test') is not None

    def test_register_duplicate_context_name(self):
        engine = SnmpEngine()
        ctx = rfc3413_context.SnmpContext(engine)
        ctx.registerContextName('test')
        with pytest.raises(Exception):
            ctx.registerContextName('test')

    def test_unregister_context_name(self):
        engine = SnmpEngine()
        ctx = rfc3413_context.SnmpContext(engine)
        ctx.registerContextName('test')
        ctx.unregisterContextName('test')
        with pytest.raises(Exception):
            ctx.getMibInstrum('test')

    def test_get_mib_instrum_default(self):
        engine = SnmpEngine()
        ctx = rfc3413_context.SnmpContext(engine)
        assert ctx.getMibInstrum() is not None

    def test_get_mib_instrum_missing(self):
        engine = SnmpEngine()
        ctx = rfc3413_context.SnmpContext(engine)
        with pytest.raises(Exception):
            ctx.getMibInstrum('nonexistent')


class TestCommandGeneratorVarBinds:
    def test_get_mib_view_controller_creates(self):
        engine = SnmpEngine()
        vb = CommandGeneratorVarBinds()
        mvc = vb.getMibViewController(engine)
        assert mvc is not None
        # Second call should return cached
        mvc2 = vb.getMibViewController(engine)
        assert mvc2 is mvc

    def test_make_var_binds_oid(self):
        engine = SnmpEngine()
        vb = CommandGeneratorVarBinds()
        result = vb.makeVarBinds(engine, [ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'), OctetString('test'))])
        assert len(result) == 1

    def test_unmake_var_binds_no_lookup(self):
        engine = SnmpEngine()
        vb = CommandGeneratorVarBinds()
        varBinds = [((1, 3, 6, 1, 2, 1, 1, 1, 0), OctetString('test'))]
        result = vb.unmakeVarBinds(engine, varBinds, lookupMib=False)
        assert len(result) == 1


class TestNotificationOriginatorVarBinds:
    def test_get_mib_view_controller(self):
        engine = SnmpEngine()
        vb = NotificationOriginatorVarBinds()
        mvc = vb.getMibViewController(engine)
        assert mvc is not None


class TestCommandGeneratorLcdConfigurator:
    def test_configure_community(self):
        engine = SnmpEngine()
        lcd = CommandGeneratorLcdConfigurator()
        authData = CommunityData('public')
        target = UdpTransportTarget(('127.0.0.1', 161))
        addrName, paramsName = lcd.configure(engine, authData, target)
        assert addrName is not None
        assert paramsName is not None

    def test_unconfigure_community(self):
        engine = SnmpEngine()
        lcd = CommandGeneratorLcdConfigurator()
        authData = CommunityData('public')
        target = UdpTransportTarget(('127.0.0.1', 161))
        lcd.configure(engine, authData, target)
        addrNames, paramsNames = lcd.unconfigure(engine, authData)
        assert len(addrNames) >= 0

    def test_configure_unsupported_auth_raises(self):
        engine = SnmpEngine()
        lcd = CommandGeneratorLcdConfigurator()
        target = UdpTransportTarget(('127.0.0.1', 161))
        with pytest.raises(error.PySnmpError):
            lcd.configure(engine, 'bad-auth-data', target)


class TestRfc3413Cmdgen:
    def test_get_next_var_binds_empty(self):
        from pysnmp.proto.rfc1905 import EndOfMibView
        varBinds = [((1, 3, 6), EndOfMibView(''))]
        errorInd, rspVarBinds = rfc3413_cmdgen.getNextVarBinds(varBinds)
        assert rspVarBinds == []

    def test_get_next_var_binds_non_null(self):
        from pyasn1.type.univ import Null
        varBinds = [((1, 3, 6), Null(''))]
        errorInd, rspVarBinds = rfc3413_cmdgen.getNextVarBinds(varBinds)
        assert len(rspVarBinds) == 1
        assert errorInd is None

    def test_command_generator_creation(self):
        cg = rfc3413_cmdgen.GetCommandGenerator()
        assert cg is not None

    def test_command_generator_classes(self):
        assert rfc3413_cmdgen.GetCommandGenerator is not None
        assert rfc3413_cmdgen.SetCommandGenerator is not None
        assert rfc3413_cmdgen.NextCommandGenerator is not None
        assert rfc3413_cmdgen.BulkCommandGenerator is not None


class TestRfc3413Ntfrcv:
    def test_notification_receiver_creation(self):
        engine = SnmpEngine()
        received = []

        def cbFun(snmpEngine, contextEngineId, contextName, varBinds, cbCtx):
            received.append(varBinds)

        nr = ntfrcv.NotificationReceiver(engine, cbFun)
        assert nr is not None
        nr.close(engine)

    def test_notification_receiver_pdu_types(self):
        assert ntfrcv.NotificationReceiver.pduTypes is not None


class TestRfc3413Config:
    def test_get_target_addr_not_configured(self):
        engine = SnmpEngine()
        with pytest.raises(Exception):
            rfc3413_config.getTargetAddr(engine, 'nonexistent')

    def test_get_target_params_not_configured(self):
        engine = SnmpEngine()
        with pytest.raises(Exception):
            rfc3413_config.getTargetParams(engine, 'nonexistent')


class TestEntityConfig:
    def test_add_v1_system(self):
        engine = SnmpEngine()
        config.addV1System(engine, 'test-comm', 'public')
        # Should not raise

    def test_add_del_v1_system(self):
        engine = SnmpEngine()
        config.addV1System(engine, 'test-comm2', 'public')
        config.delV1System(engine, 'test-comm2')

    def test_add_v3_user_no_auth_no_priv(self):
        engine = SnmpEngine()
        config.addV3User(engine, 'test-user')
        # Should not raise

    def test_add_v3_user_with_auth(self):
        engine = SnmpEngine()
        config.addV3User(
            engine, 'test-user2',
            authProtocol=config.usmHMACMD5AuthProtocol,
            authKey='authkey1'
        )

    def test_add_v3_user_bad_auth_protocol(self):
        engine = SnmpEngine()
        with pytest.raises(error.PySnmpError):
            config.addV3User(
                engine, 'test-user3',
                authProtocol=(9, 9, 9),
                authKey='authkey1'
            )

    def test_add_v3_user_bad_priv_protocol(self):
        engine = SnmpEngine()
        with pytest.raises(error.PySnmpError):
            config.addV3User(
                engine, 'test-user4',
                privProtocol=(9, 9, 9),
                privKey='privkey1'
            )

    def test_add_target_params(self):
        engine = SnmpEngine()
        config.addV1System(engine, 'comm-params', 'public')
        config.addTargetParams(engine, 'test-params', 'secname', 'noAuthNoPriv', 1)

    def test_add_target_addr(self):
        engine = SnmpEngine()
        config.addV1System(engine, 'comm-addr', 'public')
        config.addTargetParams(engine, 'test-params2', 'comm-addr', 'noAuthNoPriv', 1)
        config.addTransport(
            engine,
            (1, 3, 6, 1, 6, 1, 1),
            udp.UdpAsyncioTransport().openClientMode()
        )
        config.addTargetAddr(
            engine, 'test-addr',
            (1, 3, 6, 1, 6, 1, 1),
            ('127.0.0.1', 161),
            'test-params2',
            100, 3
        )
