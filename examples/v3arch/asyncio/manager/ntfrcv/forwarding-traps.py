"""
Forwarding notifications to other tools
+++++++++++++++++++++++++++++++++++++++

Receive SNMP TRAP/INFORM messages and relay each one to any number of
downstream tools, with the following options:

* SNMPv1/SNMPv2c
* with SNMP community "public"
* over IPv4/UDP, listening at 127.0.0.1:162
* relaying to 127.0.0.1:1162 (everything) and 127.0.0.1:1163 (link state
  notifications from 127.0.0.0/8 only)
* using Asyncio framework for network transport

162 is where a relay listens, which is why it is what this example binds --
and it is a privileged port, so run this as root or change `LISTEN_AT` below
to something above 1024 and put the same port in the `snmptrap` commands.

A notification receiver hands the application the bindings an SMIv2
notification carries -- an SNMPv1 trap arrives converted, per :RFC:`2576`
section 3.1 -- so forwarding is a matter of sending those same bindings on
rather than building a notification from scratch. `sysUpTime.0` and
`snmpTrapOID.0` stay at the front where :RFC:`3416` wants them, and the
original agent's uptime is relayed rather than this relay's.

Two things are worth copying out of this example and into anything real.

*Do not send from the receiving callback.* It runs on the event loop, and a
downstream tool that stops answering would otherwise stall the socket every
other tool's notifications arrive on. The callback only queues.

*Give each destination its own queue.* A bounded queue per destination is what
makes one unreachable tool cost that tool its notifications and nothing else.
A shared queue spreads the stall to everyone.

Either of the following Net-SNMP commands will send a notification into the
relay:

| $ snmptrap -v2c -c public 127.0.0.1 123 1.3.6.1.6.3.1.1.5.3 1.3.6.1.2.1.2.2.1.1.3 i 3
| $ snmptrap -v1 -c public 127.0.0.1 1.3.6.1.4.1.20408.4.1.1.2 0.0.0.0 6 432 12345 1.3.6.1.2.1.1.1.0 s "my system"

To see what comes out the other side, run `multiple-interfaces.py` with one of
its listening ports changed to 1162, which is where the first destination below
sends.

"""  #

import asyncio
import ipaddress
import logging

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    sendNotification,
)
from pysnmp.proto.api import v2c

# snmpTrapOID.0 names the notification; snmpTrapAddress.0 is where a relayed
# one records who actually sent it, since the downstream tool sees this relay
# as the sender.
SNMP_TRAP_OID = v2c.apiTrapPDU.snmpTrapOID
SNMP_TRAP_ADDRESS = v2c.apiTrapPDU.snmpTrapAddress

# linkDown and linkUp, the subset one of the destinations below asks for.
LINK_STATE = ("1.3.6.1.6.3.1.1.5.3", "1.3.6.1.6.3.1.1.5.4")

# Where notifications arrive. Binding 162 needs privilege; an unprivileged port
# works the same way, and the `snmptrap` commands above have to name it too.
LISTEN_AT = ("127.0.0.1", 162)

log = logging.getLogger("forwarder")


class Destination:
    """One downstream tool, the subset it wants, and the queue it reads from.

    `match` is called with the source address and the bindings of each
    notification and says whether this destination should see it. Anything
    goes: the trap OID, the sending agent, the value of a binding.
    """

    def __init__(
        self, name, address, auth=None, notifyType="trap", match=None, queueSize=1000
    ):
        self.name = name
        self.address = address
        self.auth = auth or CommunityData("public", mpModel=1)
        self.notifyType = notifyType
        self.match = match or (lambda sourceAddress, varBinds: True)
        self.queue = asyncio.Queue(maxsize=queueSize)
        self.sent = self.dropped = self.failed = 0


def trapOid(varBinds):
    """The notification's own OID, which is what a filter usually turns on."""
    for oid, value in varBinds:
        if oid == SNMP_TRAP_OID:
            return str(value)

    return ""


def fromNetwork(cidr):
    """Match notifications sent by an agent in `cidr`."""
    network = ipaddress.ip_network(cidr)

    def match(sourceAddress, varBinds):
        return ipaddress.ip_address(sourceAddress) in network

    return match


def oneOf(*oids):
    """Match notifications whose snmpTrapOID.0 is one of `oids`."""

    def match(sourceAddress, varBinds):
        return trapOid(varBinds) in oids

    return match


def both(first, second):
    """Match what `first` and `second` both match."""
    return lambda sourceAddress, varBinds: (
        first(sourceAddress, varBinds) and second(sourceAddress, varBinds)
    )


def relayed(sourceAddress, varBinds):
    """The bindings to send on, with the original sender recorded.

    A downstream tool sees the relay's address as the sender, so
    `snmpTrapAddress.0` is what tells it where the notification really came
    from. An SNMPv1 trap already carries one -- holding the agent address the
    sender put in the PDU, which is 0.0.0.0 from most stacks and wrong behind
    NAT -- so that one is replaced where it says nothing and kept where it
    does.
    """
    forwarded = []
    stamped = False

    for oid, value in varBinds:
        if oid == SNMP_TRAP_ADDRESS:
            stamped = True
            if value.prettyPrint() in ("0.0.0.0", ""):
                value = v2c.IpAddress(sourceAddress)

        forwarded.append(ObjectType(ObjectIdentity(oid), value))

    if not stamped:
        forwarded.append(
            ObjectType(ObjectIdentity(SNMP_TRAP_ADDRESS), v2c.IpAddress(sourceAddress))
        )

    return forwarded


async def forward(snmpEngine, destination):
    """Send what lands in one destination's queue, for as long as it lands.

    One task per destination, so a tool that stops answering delays nothing
    but its own.
    """
    transportTarget = UdpTransportTarget(destination.address, timeout=2, retries=1)
    contextData = ContextData()

    while True:
        sourceAddress, varBinds = await destination.queue.get()

        try:
            errorIndication, errorStatus, errorIndex, _ = await sendNotification(
                snmpEngine,
                destination.auth,
                transportTarget,
                contextData,
                destination.notifyType,
                relayed(sourceAddress, varBinds),
            )

            if errorIndication or errorStatus:
                destination.failed += 1
                log.warning("%s: %s", destination.name, errorIndication or errorStatus)
            else:
                destination.sent += 1

        except Exception:
            destination.failed += 1
            log.exception("forwarding to %s failed", destination.name)

        finally:
            destination.queue.task_done()


async def main():
    """Listen, and relay what arrives to the destinations that asked for it."""
    destinations = [
        Destination("archive", ("127.0.0.1", 1162)),
        Destination(
            "netops",
            ("127.0.0.1", 1163),
            match=both(fromNetwork("127.0.0.0/8"), oneOf(*LINK_STATE)),
        ),
    ]

    # Two engines: one bound to the listening socket, one sending. Keeping them
    # apart keeps the credentials this relay accepts separate from the ones it
    # sends under, and gives the relayed notifications this relay's own engine
    # ID rather than the receiving side's.
    receivingEngine = engine.SnmpEngine()
    sendingEngine = SnmpEngine()

    config.addTransport(
        receivingEngine,
        udp.domainName + (1,),
        udp.UdpTransport().openServerMode(LISTEN_AT),
    )
    config.addV1System(receivingEngine, "my-area", "public")

    # noinspection PyUnusedLocal
    def cbFun(
        snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx
    ):
        # The sending agent's address is not in the PDU; the dispatcher has it.
        transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo(
            stateReference
        )
        notification = (transportAddress[0], tuple(varBinds))

        for destination in destinations:
            if not destination.match(notification[0], notification[1]):
                continue

            try:
                destination.queue.put_nowait(notification)
            except asyncio.QueueFull:
                # The destination is not keeping up. Shedding its load here is
                # what stops it from becoming everyone's problem.
                destination.dropped += 1
                log.warning("%s is not keeping up, dropped one", destination.name)

    ntfrcv.NotificationReceiver(receivingEngine, cbFun)

    await asyncio.gather(
        *(forward(sendingEngine, destination) for destination in destinations)
    )


asyncio.run(main())
