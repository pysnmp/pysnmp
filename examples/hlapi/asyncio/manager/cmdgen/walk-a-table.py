#!/usr/bin/env python3
"""
Walk a table
++++++++++++

Walk one subtree with SNMP GETNEXT using the following options:

* with SNMPv2c, community 'public'
* over IPv4/UDP
* to an Agent at demo.pysnmp.com:161
* for all objects under IF-MIB::ifTable
* stopping at the end of that subtree rather than running on into the next one
* based on asyncio I/O framework

`walk_cmd()` reissues GETNEXT until the subtree runs out. `next_cmd()` is the
single request underneath it, and being lexicographic over the whole MIB it
walks straight past the end of whatever was asked for -- which is what makes
hand-written walks report rows the caller never wanted.

Functionally similar to:

| $ snmpwalk -v2c -c public demo.pysnmp.com IF-MIB::ifTable

"""  #

import asyncio

from pysnmp.hlapi.asyncio import *


async def run():
    snmpEngine = SnmpEngine()

    async for errorIndication, errorStatus, errorIndex, varBinds in walk_cmd(
        snmpEngine,
        CommunityData("public"),
        UdpTransportTarget(("demo.pysnmp.com", 161)),
        ContextData(),
        ObjectType(ObjectIdentity("IF-MIB", "ifTable")),
    ):
        if errorIndication:
            print(errorIndication)
            break

        if errorStatus:
            print(
                "{} at {}".format(
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                )
            )
            break

        for varBind in varBinds:
            print(" = ".join([x.prettyPrint() for x in varBind]))

    snmpEngine.closeDispatcher()


asyncio.run(run())
