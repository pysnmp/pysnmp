"""End-to-end checks against the real Net-SNMP CI agent."""

import os

import pytest

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    nextCmd,
    usmAesCfb128Protocol,
    usmDESPrivProtocol,
    usmHMACSHAAuthProtocol,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("NETSNMP_PROFILE"),
    reason="Net-SNMP integration agent is only available in the CI matrix.",
)

MIB2_ROOT = "1.3.6.1.2.1"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
IF_NUMBER = "1.3.6.1.2.1.2.1.0"


def credentials():
    profile = os.environ["NETSNMP_PROFILE"]
    if profile == "v1":
        return CommunityData("ci-v1-community", mpModel=0)
    if profile == "v2c":
        return CommunityData("ci-v2c-community", mpModel=1)
    if profile == "v3-noauth":
        return UsmUserData("ci-noauth")
    if profile == "v3-sha":
        return UsmUserData("ci-sha", "ciAuthPass123", authProtocol=usmHMACSHAAuthProtocol)
    if profile == "v3-aes":
        return UsmUserData(
            "ci-aes",
            "ciAuthPass123",
            "ciPrivPass123",
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmAesCfb128Protocol,
        )
    if profile == "v3-des":
        return UsmUserData(
            "ci-des",
            "ciAuthPass123",
            "ciPrivPass123",
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmDESPrivProtocol,
        )
    raise AssertionError(f"Unknown NETSNMP_PROFILE: {profile}")


def target():
    return UdpTransportTarget(("127.0.0.1", 1161), timeout=1, retries=2)


def assert_success(result):
    error_indication, error_status, error_index, var_binds = result
    assert error_indication is None
    assert not error_status, f"{error_status.prettyPrint()} at index {error_index}"
    return var_binds


def test_system_uptime_and_interface_count():
    var_binds = assert_success(
        next(
            getCmd(
                SnmpEngine(),
                credentials(),
                target(),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_UPTIME)),
                ObjectType(ObjectIdentity(IF_NUMBER)),
            )
        )
    )
    assert len(var_binds) == 2
    assert str(var_binds[0][0]) == SYS_UPTIME
    assert str(var_binds[1][0]) == IF_NUMBER


def test_mib2_walk_starts_with_system_group():
    var_binds = assert_success(
        next(
            nextCmd(
                SnmpEngine(),
                credentials(),
                target(),
                ContextData(),
                ObjectType(ObjectIdentity(MIB2_ROOT)),
                lookupMib=False,
            )
        )
    )
    assert str(var_binds[0][0]).startswith(f"{MIB2_ROOT}.")
