"""
Device report
+++++++++++++

Query a device via SNMP and print a structured report of its system
information, including description, vendor OID, uptime, contact, name,
location, services, and implemented MIB modules (sysORTable).

Functionally similar to:

| $ snmpget -v2c -c public demo.pysnmp.com SNMPv2-MIB::sysDescr.0 \\
      SNMPv2-MIB::sysObjectID.0 SNMPv2-MIB::sysUpTime.0
| $ snmpwalk -v2c -c public demo.pysnmp.com SNMPv2-MIB::sysORTable

"""  #

import asyncio

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    SnmpEngine,
    UdpTransportTarget,
    get_device_report,
)


async def run():
    report = await get_device_report(
        SnmpEngine(),
        CommunityData("public"),
        UdpTransportTarget(("demo.pysnmp.com", 161)),
        ContextData(),
    )

    print("=== Device Report ===")
    print(f"Description : {report.description}")
    print(f"Vendor OID  : {report.vendor_oid}")
    print(f"Uptime      : {report.uptime} centiseconds")
    print(f"Contact     : {report.contact}")
    print(f"Name        : {report.name}")
    print(f"Location    : {report.location}")
    print(f"Services    : {report.services}")

    if report.implemented_mibs:
        print("\nImplemented MIBs (sysORTable):")
        for mib in report.implemented_mibs:
            print(f"  [{mib.index}] {mib.or_id}")
            print(f"       {mib.or_descr}")
            print(f"       uptime: {mib.or_uptime}")
    else:
        print("\nNo sysORTable entries found.")


asyncio.run(run())
