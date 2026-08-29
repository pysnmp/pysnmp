#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Helpers for collecting standard SNMP device details."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

from pysnmp.hlapi.asyncio.cmdgen import getCmd, nextCmd
from pysnmp.proto.rfc1905 import EndOfMibView, NoSuchInstance, NoSuchObject
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

__all__ = [
    "DeviceReport",
    "SysOREntry",
    "get_device_report",
    "getDeviceReport",
]


@dataclass(frozen=True)
class SysOREntry:
    """A row from SNMPv2-MIB::sysORTable."""

    index: int
    or_id: str
    or_descr: str
    or_uptime: int


class DeviceReport(NamedTuple):
    """Structured device details gathered from SNMPv2-MIB."""

    description: str | None
    vendor_oid: str | None
    uptime: int | None
    contact: str | None
    name: str | None
    location: str | None
    services: int | None
    implemented_mibs: list[SysOREntry]


_MISSING_VALUES = (NoSuchObject, NoSuchInstance, EndOfMibView)
_SYS_OR_PREFIXES = (
    (1, 3, 6, 1, 2, 1, 1, 9, 1, 1),
    (1, 3, 6, 1, 2, 1, 1, 9, 1, 2),
    (1, 3, 6, 1, 2, 1, 1, 9, 1, 3),
    (1, 3, 6, 1, 2, 1, 1, 9, 1, 4),
)


def _available_value(value: Any) -> bool:
    return not isinstance(value, _MISSING_VALUES)


async def get_device_report(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    **options: Any,
) -> DeviceReport:
    """Query standard system objects and ``sysORTable`` from an SNMP agent.

    Unavailable scalar objects are represented by ``None``. Transport and
    protocol errors also produce a partial report rather than raising.
    ``lookupMib`` is passed through to the underlying HLAPI commands.
    """
    lookup_mib = options.get("lookupMib", True)
    scalar_fields = (
        "description",
        "vendor_oid",
        "uptime",
        "contact",
        "name",
        "location",
        "services",
    )
    scalar_var_binds = [
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysObjectID", 0)),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysUpTime", 0)),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysContact", 0)),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysName", 0)),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysLocation", 0)),
        ObjectType(ObjectIdentity("SNMPv2-MIB", "sysServices", 0)),
    ]
    results: dict[str, Any] = {}

    error_indication, error_status, _error_index, var_binds = await getCmd(
        snmpEngine,
        authData,
        transportTarget,
        contextData,
        *scalar_var_binds,
        lookupMib=lookup_mib,
    )

    if not error_indication and not error_status:
        for field, var_bind in zip(scalar_fields, var_binds):
            value = var_bind[1]
            if _available_value(value):
                results[field] = value
    elif not error_indication:
        # SNMPv1 reports a missing scalar as a PDU-level error for the whole
        # request, so retry each object separately to retain a partial report.
        for field, original_var_bind in zip(scalar_fields, scalar_var_binds):
            indication, status, _index, response = await getCmd(
                snmpEngine,
                authData,
                transportTarget,
                contextData,
                original_var_bind,
                lookupMib=lookup_mib,
            )
            if not indication and not status and response:
                value = response[0][1]
                if _available_value(value):
                    results[field] = value

    implemented_mibs: list[SysOREntry] = []
    if not error_indication:
        current_var_binds = [
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysORIndex")),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysORID")),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysORDescr")),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysORUpTime")),
        ]
        previous_index = -1

        # GETNEXT works with SNMPv1 as well as SNMPv2c/v3 and avoids having
        # separate table-walk implementations for the supported versions.
        while current_var_binds:
            indication, status, _index, table = await nextCmd(
                snmpEngine,
                authData,
                transportTarget,
                contextData,
                *current_var_binds,
                lookupMib=lookup_mib,
            )
            if indication or status or not table:
                break

            row = table[0]
            if len(row) != len(_SYS_OR_PREFIXES):
                break

            row_oids = [tuple(var_bind[0].getOid()) for var_bind in row]
            values = [var_bind[1] for var_bind in row]
            if any(not _available_value(value) for value in values):
                break

            indexes = []
            for oid, prefix in zip(row_oids, _SYS_OR_PREFIXES):
                if oid[: len(prefix)] != prefix or len(oid) != len(prefix) + 1:
                    break
                indexes.append(oid[-1])
            else:
                if len(set(indexes)) != 1 or indexes[0] <= previous_index:
                    break
                previous_index = indexes[0]
                implemented_mibs.append(
                    SysOREntry(
                        index=previous_index,
                        or_id=str(values[1]),
                        or_descr=str(values[2]),
                        or_uptime=int(values[3]),
                    )
                )
                current_var_binds = row
                continue

            break

    def as_text(field: str) -> str | None:
        value = results.get(field)
        return str(value) if value is not None else None

    def as_integer(field: str) -> int | None:
        value = results.get(field)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return DeviceReport(
        description=as_text("description"),
        vendor_oid=as_text("vendor_oid"),
        uptime=as_integer("uptime"),
        contact=as_text("contact"),
        name=as_text("name"),
        location=as_text("location"),
        services=as_integer("services"),
        implemented_mibs=implemented_mibs,
    )


# Preserve the camel-case spelling used by this branch's legacy HLAPI.
getDeviceReport = get_device_report
