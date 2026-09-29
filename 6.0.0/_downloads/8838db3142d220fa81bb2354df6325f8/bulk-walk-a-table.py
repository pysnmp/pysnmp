#!/usr/bin/env python3
"""
Bulk walk a table
+++++++++++++++++

Walk one subtree with SNMP GETBULK using the following options:

* with SNMPv2c, community 'public'
* over IPv4/UDP
* to an Agent at demo.pysnmp.com:161
* for all objects under IF-MIB::ifTable
* 25 rows per request
* stopping at the end of that subtree, with the overshoot trimmed
* based on asyncio I/O framework

An agent answering GETBULK fills `maxRepetitions` rows whether or not they
belong to the subtree asked for, so the last response of a table walk routinely
runs past the end of it. `bulk_walk_cmd()` trims that tail; `bulk_cmd()`, being
the single request underneath, hands it back.

Being an async generator, this can also be stopped early -- leave the loop and
no further request is sent.

Functionally similar to:

| $ snmpbulkwalk -v2c -c public -Cn0 -Cr25 demo.pysnmp.com IF-MIB::ifTable

"""  #

import asyncio

from pysnmp.hlapi.asyncio import *


async def run():
    snmpEngine = SnmpEngine()

    async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
        snmpEngine,
        CommunityData("public"),
        UdpTransportTarget(("demo.pysnmp.com", 161)),
        ContextData(),
        0,
        25,
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
