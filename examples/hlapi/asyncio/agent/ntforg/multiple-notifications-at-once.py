"""
Multiple concurrent notifications
+++++++++++++++++++++++++++++++++

Send multiple SNMP notifications at once using the following options:

* SNMPv2c and SNMPv3
* with community name 'public'
* over IPv4/UDP
* send INFORM notification
* to multiple Managers
* with TRAP ID 'coldStart' specified as a MIB symbol
* include managed object information specified as var-bind objects pair

Here we tag each SNMP-COMMUNITY-MIB::snmpCommunityTable row
with the same tag as SNMP-TARGET-MIB::snmpTargetAddrTable row
what leads to excessive tables information.

Functionally similar to:

| $ snmptrap -v2c -c public localhost 12345 1.3.6.1.6.3.1.1.5.2
| $ snmpinform -v2c -c public localhost 12345 1.3.6.1.6.3.1.1.5.2
| $ snmptrap -v2c -c public localhost 12345 1.3.6.1.6.3.1.1.5.2

"""  #
import asyncio
from pysnmp.hlapi.asyncio import *


async def sendone(snmpEngine, hostname, notifyType):
    trap_result = await sendNotification(
        snmpEngine,
        CommunityData("public", tag=hostname),
        UdpTransportTarget((hostname, 161), tagList=hostname),
        ContextData(),
        notifyType,
        NotificationType(ObjectIdentity("1.3.6.1.6.3.1.1.6.1.0")).addVarBinds(
            ("1.3.6.1.2.1.1.1.0", OctetString("my system"))
        ),
    )

    (errorIndication, errorStatus, errorIndex, varBinds) = await trap_result
    if errorIndication:
        print(errorIndication)
    elif errorStatus:
        print(
            "{}: at {}".format(
                errorStatus.prettyPrint(),
                errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
            )
        )
    else:
        for varBind in varBinds:
            print(" = ".join([x.prettyPrint() for x in varBind]))


snmpEngine = SnmpEngine()

asyncio.run(
    asyncio.wait(
        [
            sendone(snmpEngine, "localhost", "trap"),
            sendone(snmpEngine, "localhost", "inform"),
        ]
    )
)
