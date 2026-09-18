#!/usr/bin/env python3
"""
SNMP over TCP
+++++++++++++

Send SNMP GET request using the following options:

  * with SNMPv2c, community 'public'
  * over IPv4/TCP (:RFC:`3430`)
  * to an Agent at localhost:161
  * for an instance of SNMPv2-MIB::sysDescr.0 MIB object
  * Based on asyncio I/O framework

Functionally similar to:

| $ snmpget -v2c -c public tcp:localhost:161 SNMPv2-MIB::sysDescr.0

TCP is worth reaching for when a response would be too large to be sure of
over a datagram -- a wide GETBULK that would otherwise fragment or come back
`tooBig` -- when the path filters UDP or sits behind a stateful NAT, or when
the caller needs to tell a device that declined to answer from one it could
not reach. Over UDP those look alike: both are silence. Here a refused
connection comes back as a `transportFailure` error indication instead of
waiting out the retry schedule.

Both ends have to support it, and the agent has to be listening on TCP.
:RFC:`3430` is a transport mapping only -- it implies no security of its own,
so use SNMPv3 with authPriv where the traffic needs protecting.

"""  #

import asyncio

from pysnmp.hlapi.asyncio import *


async def run():
    snmpEngine = SnmpEngine()
    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        snmpEngine,
        CommunityData("public"),
        TcpTransportTarget(("localhost", 161)),
        ContextData(),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
    )

    if errorIndication:
        print(errorIndication)
    elif errorStatus:
        print(
            "{} at {}".format(
                errorStatus.prettyPrint(),
                errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
            )
        )
    else:
        for varBind in varBinds:
            print(" = ".join([x.prettyPrint() for x in varBind]))

    snmpEngine.transportDispatcher.closeDispatcher()


asyncio.run(run())
