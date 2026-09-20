#!/usr/bin/env python3
"""
Listening on UDP and TCP at once
++++++++++++++++++++++++++++++++

Serve SNMP requests over both transport mappings from one engine:

  * SNMPv2c, community 'public'
  * over IPv4/UDP, on 127.0.0.1:161
  * and over IPv4/TCP (:RFC:`3430`), on 127.0.0.1:161
  * serving the whole MIB tree the engine has

Functionally similar to a Net-SNMP agent configured with:

| agentAddress udp:161,tcp:161

The one thing to get right is the event loop. A transport built outside a
running loop makes a loop of its own, and every transport registered with a
dispatcher has to share the loop the dispatcher runs -- otherwise only one of
them would ever read. So name a loop and hand it to both; the dispatcher
refuses a mismatch rather than going quietly deaf on one transport.

"""  #

import asyncio

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.carrier.asyncio.stream import tcp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import cmdrsp, context

# One loop, shared by every transport on this engine.
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

snmpEngine = engine.SnmpEngine()

config.addTransport(
    snmpEngine,
    udp.domainName,
    udp.UdpTransport(loop=loop).openServerMode(("127.0.0.1", 161)),
)

config.addTransport(
    snmpEngine,
    tcp.domainName,
    tcp.TcpTransport(loop=loop).openServerMode(("127.0.0.1", 161)),
)

config.addV1System(snmpEngine, "my-area", "public")

config.addVacmUser(
    snmpEngine,
    2,
    "my-area",
    "noAuthNoPriv",
    readSubTree=(1, 3, 6, 1, 2, 1),
)

snmpContext = context.SnmpContext(snmpEngine)

cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
cmdrsp.NextCommandResponder(snmpEngine, snmpContext)
cmdrsp.BulkCommandResponder(snmpEngine, snmpContext)

snmpEngine.transportDispatcher.jobStarted(1)

try:
    snmpEngine.transportDispatcher.runDispatcher()

except Exception:
    snmpEngine.transportDispatcher.closeDispatcher()
    raise
