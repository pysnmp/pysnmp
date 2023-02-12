#!/usr/bin/env python3
"""
Concurrent queries
++++++++++++++++++

Send multiple SNMP GET requests at once using the following options:

* with SNMPv2c, community 'public'
* over IPv4/UDP
* to multiple Agents at localhost
* for instance of SNMPv2-MIB::sysDescr.0 MIB object
* based on asyncio I/O framework

Functionally similar to:

| $ snmpget -v2c -c public localhost:161 SNMPv2-MIB::sysDescr.0
| $ snmpget -v2c -c public localhost:162 SNMPv2-MIB::sysDescr.0
| $ snmpget -v2c -c public localhost:163 SNMPv2-MIB::sysDescr.0

"""  #
import asyncio
from pysnmp.hlapi.asyncio import *


async def getone(snmpEngine, hostname):
    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        snmpEngine,
        CommunityData("public"),
        UdpTransportTarget(hostname),
        ContextData(),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
    )

    if errorIndication:
        print(f'{hostname}: {errorIndication}')
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


snmpEngine = SnmpEngine()


async def main():
    await asyncio.gather(
        getone(snmpEngine, ("localhost", 161)),
        getone(snmpEngine, ("localhost6", 161)),
        getone(snmpEngine, ("localhost", 163)),
    )


asyncio.run(main())
