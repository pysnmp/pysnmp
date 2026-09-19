"""A trap and a poll, carried out end to end over loopback UDP.

These live apart from the tests that call them because two suites call them.
:py:mod:`tests.test_end_to_end` runs them in-process, the way an ordinary
install runs. :py:mod:`tests.test_no_pysmi` runs them again in a subprocess
that cannot import pysmi, which is what a stock ``pip install pysnmplib`` is.

That second suite is the reason this file exists. Until it ran an operation it
only ran configuration, and configuration is not where a pysmi-less install
broke: ``addTargetAddr()`` reaches for ``SNMPv2-TM`` and
``TRANSPORT-ADDRESS-MIB`` and ``addNotificationTarget()`` for
``SNMP-NOTIFICATION-MIB``, so an engine started, a user configured, and then
the first trap or the first GET raised ``MibNotFoundError``. A test that sends
a trap and one that polls an agent are what notice that; a test that configures
one does not.

Nothing here reaches the network: both sides of each exchange are engines in
this process, bound to 127.0.0.1 on a port the OS picked.
"""

import asyncio
import socket

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import cmdrsp, context, ntfrcv
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
    send_notification,
)

#: sysUpTime.0 and snmpTrapOID.0, the two an SMIv2 notification must carry.
SYS_UP_TIME = "1.3.6.1.2.1.1.3.0"
SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"

#: coldStart, and the object the poll asks for.
COLD_START = "1.3.6.1.6.3.1.1.5.1"
SYS_DESCR = "1.3.6.1.2.1.1.1.0"


def freePort() -> int:
    """A loopback UDP port nothing is bound to, as far as the OS knows."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def trapRoundTrip(mpModel: int = 1) -> list[tuple[str, str]]:
    """Send one notification to a receiver in this process, and return it.

    Args:
        mpModel: 0 for an SNMPv1 trap, 1 for SNMPv2c.

    Returns
    -------
        The bindings the receiver was handed, rendered as strings. A v1 trap
        arrives converted to SMIv2, so both models return sysUpTime.0 and
        snmpTrapOID.0 first however they were sent.
    """
    return asyncio.run(_trap(mpModel))


def pollRoundTrip() -> list[tuple[str, str]]:
    """GET sysDescr.0 from a command responder in this process.

    Returns
    -------
        The bindings the manager got back, rendered as strings.
    """
    return asyncio.run(_poll())


async def _trap(mpModel: int) -> list[tuple[str, str]]:
    port = freePort()
    received: asyncio.Queue = asyncio.Queue()

    receiver = engine.SnmpEngine()
    config.addTransport(
        receiver,
        udp.domainName + (1,),
        udp.UdpTransport().openServerMode(("127.0.0.1", port)),
    )
    config.addV1System(receiver, "area", "public")

    def cbFun(
        snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx
    ):
        received.put_nowait(
            [(str(oid), value.prettyPrint()) for oid, value in varBinds]
        )

    ntfrcv.NotificationReceiver(receiver, cbFun)

    sender = SnmpEngine()
    try:
        errorIndication, errorStatus, errorIndex, varBinds = await send_notification(
            sender,
            CommunityData("public", mpModel=mpModel),
            UdpTransportTarget(("127.0.0.1", port)),
            ContextData(),
            "trap",
            [
                ObjectType(ObjectIdentity(SYS_UP_TIME), 12345),
                ObjectType(ObjectIdentity(SNMP_TRAP_OID), COLD_START),
            ],
        )
        if errorIndication:
            raise AssertionError(f"the trap was not sent: {errorIndication}")

        return await asyncio.wait_for(received.get(), timeout=10)
    finally:
        sender.transportDispatcher.closeDispatcher()
        receiver.transportDispatcher.closeDispatcher()


async def _poll() -> list[tuple[str, str]]:
    port = freePort()

    agent = engine.SnmpEngine()
    config.addTransport(
        agent,
        udp.domainName + (1,),
        udp.UdpTransport().openServerMode(("127.0.0.1", port)),
    )
    config.addV1System(agent, "area", "public")
    config.addVacmUser(agent, 2, "area", "noAuthNoPriv", (1, 3, 6, 1, 2, 1))
    cmdrsp.GetCommandResponder(agent, context.SnmpContext(agent))

    manager = SnmpEngine()
    try:
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            manager,
            CommunityData("public", mpModel=1),
            UdpTransportTarget(("127.0.0.1", port), timeout=5, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(SYS_DESCR)),
        )
        if errorIndication:
            raise AssertionError(f"the GET failed: {errorIndication}")
        if errorStatus:
            raise AssertionError(f"the agent refused: {errorStatus.prettyPrint()}")

        return [(str(oid), value.prettyPrint()) for oid, value in varBinds]
    finally:
        manager.transportDispatcher.closeDispatcher()
        agent.transportDispatcher.closeDispatcher()
