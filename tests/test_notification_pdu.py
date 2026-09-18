"""Translating a notification PDU that arrived off the network.

RFC 3416 section 4.2.6 puts ``sysUpTime.0`` first and ``snmpTrapOID.0`` second,
so a conformant v2c notification always has at least two bindings -- but the
proxy reads its input from the wire, where nothing guarantees that.
"""

import pytest

from pysnmp.proto import api, error
from pysnmp.proto.api import v2c
from pysnmp.proto.proxy import rfc2576
from pysnmp.smi.builder import MibBuilder

PAYLOAD_A = (v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 9999, 1)), v2c.OctetString("a"))
PAYLOAD_B = (v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 9999, 2)), v2c.OctetString("b"))


@pytest.fixture(scope="module")
def notificationSymbols():
    """The two MIB instances the ordering is defined in terms of."""
    built = MibBuilder()

    return built.importSymbols("__SNMPv2-MIB", "snmpTrapOID", "sysUpTime")


@pytest.fixture
def uptimeBinding(notificationSymbols):
    _, sysUpTime = notificationSymbols

    return (
        v2c.ObjectIdentifier(sysUpTime.getName()),
        # SysUpTime.clone() takes keywords only; with no value it reads the
        # engine's uptime, and a caller's own reading is what is pinned here.
        sysUpTime.getSyntax().clone(value=4242),
    )


@pytest.fixture
def trapOidBinding(notificationSymbols):
    snmpTrapOID, _ = notificationSymbols

    return (
        v2c.ObjectIdentifier(snmpTrapOID.getName()),
        v2c.ObjectIdentifier((1, 3, 6, 1, 6, 3, 1, 1, 5, 3)),  # linkDown
    )


class TestV2ToV1TruncatedNotification:
    """The proxy's side: a malformed PDU off the network."""

    def _notification(self, varBinds):
        v2c_api = api.protoModules[api.protoVersion2c]
        pdu = v2c_api.TrapPDU()
        v2c_api.apiTrapPDU.setDefaults(pdu)
        v2c_api.apiTrapPDU.setVarBinds(pdu, varBinds)

        return pdu

    @pytest.mark.parametrize("count", [0, 1], ids=["no-var-binds", "one-var-bind"])
    def test_a_short_notification_raises_protocol_error(
        self, count, uptimeBinding, trapOidBinding
    ):
        # A conformant v2c notification always has at least two bindings, so
        # the [1] index was safe for well-formed input -- but this is a network
        # input, and a truncated one raised IndexError out of the protocol
        # layer instead of the ProtocolError every other malformed case here
        # raises.
        pdu = self._notification([uptimeBinding][:count])

        with pytest.raises(error.ProtocolError):
            rfc2576.v2ToV1(pdu)

    def test_a_second_binding_that_is_not_snmp_trap_oid_still_raises(
        self, uptimeBinding
    ):
        pdu = self._notification([uptimeBinding, PAYLOAD_A])

        with pytest.raises(error.ProtocolError, match="snmpTrapOID"):
            rfc2576.v2ToV1(pdu)

    def test_a_well_formed_notification_still_translates(
        self, uptimeBinding, trapOidBinding
    ):
        pdu = self._notification([uptimeBinding, trapOidBinding, PAYLOAD_A])

        v1Pdu = rfc2576.v2ToV1(pdu)

        assert v1Pdu is not None
        assert api.protoModules[api.protoVersion1].apiTrapPDU.getVarBinds(v1Pdu)
