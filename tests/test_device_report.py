"""Integration tests for the device-report helper."""

import asyncio

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    DeviceReport,
    SnmpEngine,
    SysOREntry,
    UdpTransportTarget,
    get_device_report,
)
from pysnmp.hlapi.asyncio import get_device_report as asyncio_get_device_report


def _assert_report(report):
    assert isinstance(report, DeviceReport)
    assert report.description == "pysnmp integration SNMPv2c agent"
    assert report.vendor_oid == "1.3.6.1.4.1.20408"
    assert report.uptime == 12345
    assert report.contact == "Test Contact"
    assert report.name == "Test Host"
    assert report.location == "Test Location"
    assert report.services == 72
    assert report.implemented_mibs == [
        SysOREntry(
            index=1,
            or_id="1.3.6.1.6.3.11.3.1.1",
            or_descr="SNMP Management Architecture MIB",
            or_uptime=123,
        ),
        SysOREntry(
            index=2,
            or_id="1.3.6.1.6.3.15.2.1.1",
            or_descr="User-based Security Model MIB",
            or_uptime=456,
        ),
    ]


def test_sync_device_report(snmpsim_endpoint):
    host, port = snmpsim_endpoint
    report = get_device_report(
        SnmpEngine(),
        CommunityData("public", mpModel=1),
        UdpTransportTarget((host, port), timeout=1, retries=2),
        ContextData(),
    )
    _assert_report(report)


def test_asyncio_device_report(snmpsim_endpoint):
    host, port = snmpsim_endpoint

    async def run():
        return await asyncio_get_device_report(
            SnmpEngine(),
            CommunityData("public", mpModel=1),
            UdpTransportTarget((host, port), timeout=1, retries=2),
            ContextData(),
        )

    _assert_report(asyncio.run(run()))


def test_snmpv1_device_report(snmpsim_endpoint):
    """GETNEXT-based sysORTable walking remains compatible with SNMPv1."""
    host, port = snmpsim_endpoint
    report = get_device_report(
        SnmpEngine(),
        CommunityData("public@1", mpModel=0),
        UdpTransportTarget((host, port), timeout=1, retries=2),
        ContextData(),
    )
    assert report.description == "pysnmp integration SNMPv1 agent"
    assert [row.index for row in report.implemented_mibs] == [1, 2]
