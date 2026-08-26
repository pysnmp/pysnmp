"""Local notification-receiver tests for trap and inform behavior."""

import socket
import time

import pytest

from pysnmp.entity.engine import SnmpEngine
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.entity import config
from pysnmp.carrier.asyncore.dispatch import AsyncoreDispatcher
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.proto.api import v2c, v1
from pysnmp.proto.rfc1905 import SNMPv2TrapPDU
from pysnmp.proto.rfc1157 import TrapPDU


def _get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestNotificationReceiver:
    """Test the NotificationReceiver class registration and PDU types."""

    def test_pdu_types(self):
        assert ntfrcv.NotificationReceiver.pduTypes is not None
        assert len(ntfrcv.NotificationReceiver.pduTypes) == 3

    def test_creation(self):
        engine = SnmpEngine()
        received = []

        def cbFun(snmpEngine, contextEngineId, contextName, varBinds, cbCtx):
            received.append(varBinds)

        nr = ntfrcv.NotificationReceiver(engine, cbFun)
        assert nr is not None
        nr.close(engine)

    def test_creation_with_cbCtx(self):
        engine = SnmpEngine()
        ctx = {"key": "value"}

        def cbFun(snmpEngine, contextEngineId, contextName, varBinds, cbCtx):
            pass

        nr = ntfrcv.NotificationReceiver(engine, cbFun, cbCtx=ctx)
        assert nr is not None
        nr.close(engine)

    def test_close(self):
        engine = SnmpEngine()

        def cbFun(snmpEngine, contextEngineId, contextName, varBinds, cbCtx):
            pass

        nr = ntfrcv.NotificationReceiver(engine, cbFun)
        nr.close(engine)
        # After close, cbFun should be None
        assert nr._NotificationReceiver__cbFun is None


class TestTrapPDUConstruction:
    """Test trap PDU construction for notification tests."""

    def test_v2c_trap_pdu(self):
        pdu = SNMPv2TrapPDU()
        v2c.apiPDU.setDefaults(pdu)
        v2c.apiPDU.setVarBinds(pdu, [
            ((1, 3, 6, 1, 2, 1, 1, 3, 0), v2c.TimeTicks(12345)),
            ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0),
             v2c.ObjectIdentifier((1, 3, 6, 1, 6, 3, 1, 1, 5, 1))),
        ])
        var_binds = v2c.apiPDU.getVarBinds(pdu)
        assert len(var_binds) == 2

    def test_v1_trap_pdu(self):
        pdu = TrapPDU()
        v1.apiTrapPDU.setDefaults(pdu)
        v1.apiTrapPDU.setGenericTrap(pdu, 0)  # coldStart
        assert int(v1.apiTrapPDU.getGenericTrap(pdu)) == 0


class TestNotificationOriginator:
    """Test the NotificationOriginator class."""

    def test_creation(self):
        from pysnmp.entity.rfc3413 import ntforg
        no = ntforg.NotificationOriginator()
        assert no is not None

    def test_send_var_binds_method_exists(self):
        from pysnmp.entity.rfc3413 import ntforg
        assert hasattr(ntforg.NotificationOriginator, "sendVarBinds")

    def test_send_pdu_method_exists(self):
        from pysnmp.entity.rfc3413 import ntforg
        assert hasattr(ntforg.NotificationOriginator, "sendPdu")