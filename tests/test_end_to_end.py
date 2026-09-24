"""A trap and a poll work, in an install that has pysmi.

The other half of :py:mod:`tests.test_no_pysmi`, which runs the same two
exchanges in a subprocess that cannot import it. Together they say that an
operation works whether or not the optional dependency is installed, which is
what nothing said before: the pysmi-less suite ran configuration calls and
stopped one call short of ``addTargetAddr()``, so a stock install could start
an engine, configure a user, and then fail on every GET and every trap it
tried to send.

Both sides of each exchange are engines in this process. Nothing here needs a
simulator, a network or a fixture beyond a free port.
"""

import pytest

from tests.end_to_end import (
    COLD_START,
    SNMP_TRAP_OID,
    SYS_DESCR,
    SYS_UP_TIME,
    pollRoundTrip,
    trapRoundTrip,
)


@pytest.mark.parametrize("mpModel", (0, 1), ids=("v1", "v2c"))
def test_a_trap_arrives_with_the_bindings_it_was_sent(mpModel):
    varBinds = dict(trapRoundTrip(mpModel))

    assert varBinds[SYS_UP_TIME] == "12345"
    assert varBinds[SNMP_TRAP_OID] == COLD_START


def test_a_v1_trap_arrives_converted_to_smiv2():
    # RFC 2576 section 3.1: the enterprise, agent address and trap numbers a v1
    # trap carries in the PDU have nowhere to go in a v2c one, so they become
    # bindings. A receiver sees one shape however the trap was sent, which is
    # what lets an application -- a forwarder, most of all -- relay what it was
    # handed without caring which version it arrived as.
    varBinds = dict(trapRoundTrip(0))

    assert "1.3.6.1.6.3.18.1.3.0" in varBinds  # snmpTrapAddress.0
    assert varBinds["1.3.6.1.6.3.18.1.4.0"] == "public"  # snmpTrapCommunity.0
    assert "1.3.6.1.6.3.1.1.4.3.0" in varBinds  # snmpTrapEnterprise.0


def test_a_v2c_trap_carries_only_what_it_was_given():
    varBinds = trapRoundTrip(1)

    assert [oid for oid, _ in varBinds] == [SYS_UP_TIME, SNMP_TRAP_OID]


def test_a_poll_returns_the_object_it_asked_for():
    ((oid, value),) = pollRoundTrip()

    assert oid == SYS_DESCR
    assert value.startswith("PySNMP engine version")
