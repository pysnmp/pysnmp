#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Realistic SNMP payloads shared by the benchmark modules."""

from pyasn1.type import univ

from pysnmp.proto import api

SNMP_ENGINE_ID = univ.OctetString(hexValue="80004fb8054265616d206d65757021")

# The system group, which is what every manager polls first.
SYSTEM_OIDS = [(1, 3, 6, 1, 2, 1, 1, idx, 0) for idx in range(1, 8)]

# A slice of ifTable: ten interfaces, six columns each. This is the kind of
# payload a GETBULK walk brings back from a real device.
IF_TABLE_OIDS = [
    (1, 3, 6, 1, 2, 1, 2, 2, 1, column, index)
    for index in range(1, 11)
    for column in (1, 2, 3, 8, 10, 16)
]


def make_request(version, oids, community="public"):
    """Build a non-encoded SNMP GetRequest message holding `oids`."""
    pMod = api.protoModules[version]

    pdu = pMod.GetRequestPDU()
    pMod.apiPDU.setDefaults(pdu)
    pMod.apiPDU.setVarBinds(pdu, [(oid, pMod.null) for oid in oids])

    msg = pMod.Message()
    pMod.apiMessage.setDefaults(msg)
    pMod.apiMessage.setCommunity(msg, community)
    pMod.apiMessage.setPDU(msg, pdu)

    return msg


def make_response(version, oids, community="public"):
    """Build a non-encoded SNMP response message with mixed value types."""
    pMod = api.protoModules[version]

    values = (
        lambda: pMod.OctetString("Linux edge-router-01 5.15.0-91-generic"),
        lambda: pMod.ObjectIdentifier((1, 3, 6, 1, 4, 1, 8072, 3, 2, 10)),
        lambda: pMod.TimeTicks(1234567),
        lambda: pMod.Integer(42),
        lambda: pMod.IpAddress("192.168.13.37"),
        lambda: (
            pMod.Gauge(0xDEADBEEF)
            if version == api.protoVersion1
            else pMod.Gauge32(0xDEADBEEF)
        ),
    )

    varBinds = [(oid, values[idx % len(values)]()) for idx, oid in enumerate(oids)]

    pdu = pMod.GetResponsePDU()
    pMod.apiPDU.setDefaults(pdu)
    pMod.apiPDU.setVarBinds(pdu, varBinds)

    msg = pMod.Message()
    pMod.apiMessage.setDefaults(msg)
    pMod.apiMessage.setCommunity(msg, community)
    pMod.apiMessage.setPDU(msg, pdu)

    return msg
