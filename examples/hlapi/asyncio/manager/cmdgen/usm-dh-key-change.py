"""
Change a USM authentication key by Diffie-Hellman agreement
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

Rotate an agent's authentication key without either key crossing the wire and
without needing the old one, per :RFC:`2786`.

The agent must implement SNMP-USM-DH-OBJECTS-MIB, and the credentials used must
have write access to the row. Net-SNMP implements it when built with the
``snmp-usm-dh-objects-mib`` module, which distribution packages usually leave out.
"""

import asyncio

from pysnmp.hlapi.asyncio import (
    ContextData,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    dh_key_change,
    getCmd,
    usmHMACSHAAuthProtocol,
    usmKeyTypeLocalized,
)
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType


async def run():
    """Rotate the key, then use the new one."""
    current = UsmUserData(
        "usr-sha-none", "authkey1", authProtocol=usmHMACSHAAuthProtocol
    )
    target = await UdpTransportTarget.create(("demo.pysnmp.com", 161))

    result = await dh_key_change(
        SnmpEngine(),
        current,
        target,
        ContextData(),
        "auth",
    )

    # The agent re-keyed when the SET committed, so `current` is now stale. The
    # derived key is already localized to this agent, and USM needs to be told
    # which agent that is -- both come back from the exchange.
    rekeyed = UsmUserData(
        "usr-sha-none",
        result.key,
        authProtocol=usmHMACSHAAuthProtocol,
        authKeyType=usmKeyTypeLocalized,
        securityEngineId=OctetString(result.securityEngineId),
    )

    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        SnmpEngine(),
        rekeyed,
        await UdpTransportTarget.create(("demo.pysnmp.com", 161)),
        ContextData(),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
    )

    if errorIndication:
        print(errorIndication)
    elif errorStatus:
        print(
            f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
        )
    else:
        for varBind in varBinds:
            print(" = ".join([x.prettyPrint() for x in varBind]))


asyncio.run(run())
