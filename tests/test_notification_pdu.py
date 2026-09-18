"""What a notification PDU has to look like, on the way out and on the way across.

RFC 3416 section 4.2.6: a notification carries ``sysUpTime.0`` first and
``snmpTrapOID.0`` second. Two places got that wrong -- the originator, which
reordered the caller's bindings with an off-by-one and a loop that mutated what
it was iterating, and the v2c-to-v1 proxy, which indexed past the end of a
truncated PDU that arrived off the network.
"""

import pytest

from pysnmp.entity.rfc3413.ntforg import orderNotificationVarBinds
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
def order(notificationSymbols):
    """Order var-binds the way the originator does."""
    snmpTrapOID, sysUpTime = notificationSymbols

    def run(varBinds):
        return orderNotificationVarBinds(varBinds, sysUpTime, snmpTrapOID)

    return run


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


def names(varBinds):
    return [tuple(oid) for oid, _ in varBinds]


class TestNotificationVarBindOrder:
    """The originator's reordering."""

    def test_already_ordered_bindings_are_left_alone(
        self, order, uptimeBinding, trapOidBinding
    ):
        result = order([uptimeBinding, trapOidBinding, PAYLOAD_A, PAYLOAD_B])

        assert names(result) == names(
            [uptimeBinding, trapOidBinding, PAYLOAD_A, PAYLOAD_B]
        )
        assert result[0][1] == uptimeBinding[1]

    def test_out_of_order_bindings_are_reordered_without_duplication(
        self, order, uptimeBinding, trapOidBinding
    ):
        # The reported case. Four bindings in; the old loop produced six, with
        # sysUpTime.0 and snmpTrapOID.0 each appearing twice.
        result = order([PAYLOAD_A, trapOidBinding, uptimeBinding, PAYLOAD_B])

        assert len(result) == 4
        assert names(result) == names(
            [uptimeBinding, trapOidBinding, PAYLOAD_A, PAYLOAD_B]
        )

    def test_the_callers_uptime_value_survives_the_move(
        self, order, uptimeBinding, trapOidBinding
    ):
        # Not just the name in the right slot -- the caller's *value*. The old
        # code inserted a fresh uptime at 0 and then deleted the wrong element,
        # so the caller's reading could be dropped in favour of "now".
        result = order([PAYLOAD_A, trapOidBinding, uptimeBinding])

        assert int(result[0][1]) == 4242

    def test_a_missing_uptime_is_supplied(self, order, trapOidBinding):
        result = order([trapOidBinding, PAYLOAD_A])

        assert names(result)[0] == (1, 3, 6, 1, 2, 1, 1, 3, 0)
        assert result[0][1].isValue

    def test_a_trap_oid_further_down_is_moved_into_second_place(
        self, order, uptimeBinding, trapOidBinding
    ):
        result = order([uptimeBinding, PAYLOAD_A, PAYLOAD_B, trapOidBinding])

        assert names(result) == names(
            [uptimeBinding, trapOidBinding, PAYLOAD_A, PAYLOAD_B]
        )

    def test_payload_order_is_preserved(self, order, uptimeBinding, trapOidBinding):
        result = order([PAYLOAD_B, PAYLOAD_A, trapOidBinding, uptimeBinding])

        assert names(result)[2:] == names([PAYLOAD_B, PAYLOAD_A])

    def test_no_binding_carries_an_unset_syntax(
        self, order, uptimeBinding, trapOidBinding
    ):
        result = order([PAYLOAD_A, trapOidBinding, uptimeBinding])

        assert all(value.isValue for _, value in result)

    def test_the_supplied_uptime_is_not_the_live_mib_object(
        self, order, notificationSymbols, trapOidBinding
    ):
        # Binding the MIB instance's own syntax into a PDU aliases engine state
        # into a message. It must be a clone.
        _, sysUpTime = notificationSymbols

        result = order([trapOidBinding])

        assert result[0][1] is not sysUpTime.getSyntax()

    def test_a_missing_trap_oid_is_reported(self, order, uptimeBinding):
        # This is the behaviour change. Previously a placeholder was inserted
        # carrying the live snmpTrapOID instance's value, which defaults to
        # 1.3.6.1.6.3.1.1.5.1 -- so omitting the binding silently sent a
        # coldStart rather than saying anything was wrong.
        with pytest.raises(error.PySnmpError, match="snmpTrapOID"):
            order([uptimeBinding, PAYLOAD_A])

    def test_no_var_binds_at_all_is_reported(self, order):
        # The old loop could not even reach its sysUpTime insertion here, since
        # `for idx in range(len(varBinds))` never runs on an empty list, so the
        # PDU went out with snmpTrapOID.0 alone and no sysUpTime.0.
        with pytest.raises(error.PySnmpError, match="snmpTrapOID"):
            order([])

    def test_the_callers_list_is_not_modified(
        self, order, uptimeBinding, trapOidBinding
    ):
        varBinds = [PAYLOAD_A, trapOidBinding, uptimeBinding]
        before = list(varBinds)

        order(varBinds)

        assert varBinds == before


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
