"""End-to-end checks against the real Net-SNMP CI agent.

These tests run inside the CI matrix defined by
``.github/workflows/net-snmp-integration.yml``. Each matrix profile populates
``NETSNMP_PROFILE`` and starts a fresh ``snmpd`` container configured by
``.github/ci/net-snmp/entrypoint.sh``. Locally (without the env var) the whole
module is skipped.
"""

import asyncio
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
    setCmd,
    usmAesCfb128Protocol,
    usmDESPrivProtocol,
    usmHMACSHAAuthProtocol,
)
from pysnmp.hlapi.asyncio import (
    UdpTransportTarget as AsyncUdpTransportTarget,
    bulkCmd as async_bulkCmd,
    getCmd as async_getCmd,
)
from pysnmp.proto.rfc1902 import OctetString, TimeTicks
from pysnmp.proto.rfc1905 import NoSuchInstance


pytestmark = pytest.mark.skipif(
    not os.environ.get("NETSNMP_PROFILE"),
    reason="Net-SNMP integration agent is only available in the CI matrix.",
)

# --- MIB-2 OIDs -----------------------------------------------------------
MIB2_ROOT = "1.3.6.1.2.1"
SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
SYS_NAME = "1.3.6.1.2.1.1.5.0"
SYS_LOCATION = "1.3.6.1.2.1.1.6.0"
IF_NUMBER = "1.3.6.1.2.1.2.1.0"
IF_DESCR_1 = "1.3.6.1.2.1.2.2.1.2.1"
IF_ADMIN_STATUS_1 = "1.3.6.1.2.1.2.2.1.7.1"
# A non-existent instance used to exercise noSuch* semantics.
MISSING_IF_DESCR = "1.3.6.1.2.1.2.2.1.2.999"
IF_DESCR_COLUMN = "1.3.6.1.2.1.2.2.1.2"

AGENT_HOST = ("127.0.0.1", 1161)


# --- helpers --------------------------------------------------------------
def profile():
    return os.environ["NETSNMP_PROFILE"]


def is_v1():
    return profile() == "v1"


def is_v3():
    return profile().startswith("v3")


def credentials():
    p = profile()
    if p == "v1":
        return CommunityData("ci-v1-community", mpModel=0)
    if p == "v2c":
        return CommunityData("ci-v2c-community", mpModel=1)
    if p == "v3-noauth":
        return UsmUserData("ci-noauth")
    if p == "v3-sha":
        return UsmUserData("ci-sha", "ciAuthPass123", authProtocol=usmHMACSHAAuthProtocol)
    if p == "v3-aes":
        return UsmUserData(
            "ci-aes",
            "ciAuthPass123",
            "ciPrivPass123",
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmAesCfb128Protocol,
        )
    if p == "v3-des":
        return UsmUserData(
            "ci-des",
            "ciAuthPass123",
            "ciPrivPass123",
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmDESPrivProtocol,
        )
    raise AssertionError(f"Unknown NETSNMP_PROFILE: {p}")


def wrong_credentials():
    """Credentials that the agent must reject, used for negative v3 tests."""
    p = profile()
    if p == "v3-noauth":
        return UsmUserData("ci-nonexistent")
    if p == "v3-sha":
        return UsmUserData(
            "ci-sha", "WRONG-AUTH-PASS", authProtocol=usmHMACSHAAuthProtocol
        )
    if p == "v3-aes":
        return UsmUserData(
            "ci-aes",
            "WRONG-AUTH-PASS",
            "ciPrivPass123",
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmAesCfb128Protocol,
        )
    if p == "v3-des":
        return UsmUserData(
            "ci-des",
            "WRONG-AUTH-PASS",
            "ciPrivPass123",
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmDESPrivProtocol,
        )
    raise AssertionError(f"wrong_credentials() is only defined for v3 profiles, got {p}")


def target():
    return UdpTransportTarget(AGENT_HOST, timeout=2, retries=3)


def async_target():
    return AsyncUdpTransportTarget(AGENT_HOST, timeout=2, retries=3)


def assert_success(result):
    error_indication, error_status, error_index, var_binds = result
    assert error_indication is None, f"unexpected error indication: {error_indication}"
    assert not error_status, f"{error_status.prettyPrint()} at index {error_index}"
    return var_binds


def _get_one(*oids):
    """Synchronous single-shot GET of one or more OID strings."""
    return assert_success(
        next(
            getCmd(
                SnmpEngine(),
                credentials(),
                target(),
                ContextData(),
                *(ObjectType(ObjectIdentity(o)) for o in oids),
            )
        )
    )


# --- core protocol / coverage tests --------------------------------------
def test_full_mib2_walk_covers_system_and_interfaces():
    """nextCmd auto-selects GETNEXT (v1) or GETBULK (v2c/v3); the walk must
    return a healthy set of OIDs spanning the system and interfaces groups."""
    seen_system = False
    seen_interfaces = False
    rows = 0
    iterator = nextCmd(
        SnmpEngine(),
        credentials(),
        target(),
        ContextData(),
        ObjectType(ObjectIdentity(MIB2_ROOT)),
        lookupMib=False,
        maxRows=200,
    )
    for error_indication, error_status, _error_index, var_binds in iterator:
        assert error_indication is None, f"MIB-2 walk aborted: {error_indication}"
        assert not error_status, f"MIB-2 walk error: {error_status}"
        for oid, _value in var_binds:
            oid_str = str(oid)
            if oid_str.startswith(f"{MIB2_ROOT}.1."):
                seen_system = True
            elif oid_str.startswith(f"{MIB2_ROOT}.2."):
                seen_interfaces = True
            rows += 1
        # Stop early once both groups are observed to keep the matrix fast.
        if seen_system and seen_interfaces:
            break
    assert rows >= 5, f"MIB-2 walk returned too few rows: {rows}"
    assert seen_system, "walk did not reach the system group (1.3.6.1.2.1.1)"
    assert seen_interfaces, "walk did not reach the interfaces group (1.3.6.1.2.1.2)"


def test_system_uptime_is_timeticks():
    var_binds = _get_one(SYS_UPTIME)
    assert str(var_binds[0][0]) == SYS_UPTIME
    assert isinstance(var_binds[0][1], TimeTicks), (
        f"sysUpTime.0 must be TimeTicks, got {type(var_binds[0][1]).__name__}"
    )


def test_real_interface_row_is_indexed():
    """Validate indexed table access against a real interface row, not just
    the scalar ifNumber.0."""
    var_binds = _get_one(IF_DESCR_1, IF_ADMIN_STATUS_1)
    assert str(var_binds[0][0]) == IF_DESCR_1
    assert str(var_binds[1][0]) == IF_ADMIN_STATUS_1
    assert str(var_binds[0][1]).strip() != "", "ifDescr.1 was empty"
    assert int(var_binds[1][1]) in (1, 2, 3), (
        f"ifAdminStatus.1 must be up(1)/down(2)/testing(3), got {var_binds[1][1]}"
    )


def test_multi_oid_get_preserves_order():
    var_binds = _get_one(SYS_UPTIME, SYS_NAME, IF_DESCR_1)
    assert len(var_binds) == 3
    assert [str(vb[0]) for vb in var_binds] == [SYS_UPTIME, SYS_NAME, IF_DESCR_1]


def test_system_identity_is_well_formed():
    var_binds = _get_one(SYS_DESCR, SYS_OBJECT_ID, SYS_NAME)
    assert str(var_binds[0][0]) == SYS_DESCR
    assert str(var_binds[1][0]) == SYS_OBJECT_ID
    assert str(var_binds[2][0]) == SYS_NAME
    assert str(var_binds[0][1]).strip() != "", "sysDescr.0 was empty"
    assert str(var_binds[1][1]).strip() != "", "sysObjectID.0 was empty"
    assert str(var_binds[2][1]) == f"pysnmp-ci-{profile()}", (
        f"sysName.0 mismatch: {var_binds[2][1]}"
    )


# --- GETBULK / GETNEXT differentiation -----------------------------------
def test_getbulk_returns_multiple_rows_for_v2c_and_v3():
    if is_v1():
        pytest.skip("GETBULK is not available for SNMPv1; GETNEXT is covered separately")

    async def one_bulk():
        # async bulkCmd is a coroutine returning a single 4-tuple (one GETBULK
        # response), not an async generator.
        return await async_bulkCmd(
            SnmpEngine(),
            credentials(),
            async_target(),
            ContextData(),
            0,  # non-repeaters
            10,  # max-repetitions
            ObjectType(ObjectIdentity(IF_DESCR_COLUMN)),
            lookupMib=False,
        )

    error_indication, error_status, _error_index, var_bind_table = asyncio.run(one_bulk())
    assert error_indication is None, f"GETBULK failed: {error_indication}"
    assert not error_status, f"GETBULK error status: {error_status}"
    assert len(var_bind_table) >= 2, (
        f"GETBULK should return multiple interface rows, got {len(var_bind_table)}"
    )


def test_getnext_walk_progresses_for_v1():
    if not is_v1():
        pytest.skip("GETNEXT differentiation is only asserted for SNMPv1")

    oids = []
    iterator = nextCmd(
        SnmpEngine(),
        credentials(),
        target(),
        ContextData(),
        ObjectType(ObjectIdentity(MIB2_ROOT)),
        lookupMib=False,
        maxRows=5,
    )
    for error_indication, error_status, _error_index, var_binds in iterator:
        assert error_indication is None, f"GETNEXT walk aborted: {error_indication}"
        assert not error_status, f"GETNEXT walk error: {error_status}"
        for oid, _value in var_binds:
            oids.append(str(oid))
    assert len(oids) >= 3, f"GETNEXT walk should yield several rows, got {oids}"
    # GETNEXT advances the OID lexicographically; consecutive OIDs must differ.
    assert len(set(oids)) == len(oids), f"GETNEXT did not advance: {oids}"


# --- error / negative-path coverage --------------------------------------
def test_missing_oid_surfaces_nosuch_semantics():
    error_indication, error_status, error_index, var_binds = next(
        getCmd(
            SnmpEngine(),
            credentials(),
            target(),
            ContextData(),
            ObjectType(ObjectIdentity(MISSING_IF_DESCR)),
        )
    )
    if is_v1():
        # SNMPv1 reports a missing instance as a noSuchName error status.
        assert error_status, (
            f"v1 GET of a missing OID should report noSuchName, got "
            f"indication={error_indication!r} status={error_status!r}"
        )
    else:
        assert error_indication is None, error_indication
        assert not error_status, error_status
        assert isinstance(var_binds[0][1], NoSuchInstance), (
            f"v2c/v3 GET of a missing OID should yield NoSuchInstance, got "
            f"{type(var_binds[0][1]).__name__}"
        )


def test_v3_wrong_credentials_fail_cleanly():
    if not is_v3():
        pytest.skip("Negative authentication is only exercised for SNMPv3 profiles")

    error_indication, _error_status, _error_index, _var_binds = next(
        getCmd(
            SnmpEngine(),
            wrong_credentials(),
            target(),
            ContextData(),
            ObjectType(ObjectIdentity(SYS_UPTIME)),
        )
    )
    assert error_indication is not None, (
        "wrong v3 credentials must fail with an error indication, not return data"
    )


# --- SET roundtrip --------------------------------------------------------
def test_set_syslocation_roundtrip():
    """SET is the missing major request type: write sysLocation.0, read it back,
    then restore the original value. The restore runs even on assertion failure.

    Each command uses a fresh SnmpEngine because the synchronous HLAPI closes the
    engine's transport dispatcher in its ``finally`` block, so a single engine
    cannot be reused across sequential commands.
    """

    def get_location():
        var_binds = assert_success(
            next(
                getCmd(
                    SnmpEngine(),
                    credentials(),
                    target(),
                    ContextData(),
                    ObjectType(ObjectIdentity(SYS_LOCATION)),
                )
            )
        )
        return var_binds[0][1]

    def set_location(value):
        assert_success(
            next(
                setCmd(
                    SnmpEngine(),
                    credentials(),
                    target(),
                    ContextData(),
                    ObjectType(ObjectIdentity(SYS_LOCATION), value),
                )
            )
        )

    original = get_location()
    marker = OctetString(f"pysnmp-ci-{profile()}-set-marker")
    try:
        set_location(marker)
        assert str(get_location()) == str(marker), "sysLocation.0 did not take the SET value"
    finally:
        set_location(original)
        assert str(get_location()) == str(original), "sysLocation.0 was not restored"


# --- transport dispatching ------------------------------------------------
def test_concurrent_requests_all_succeed():
    """Issue a modest batch of simultaneous GETs to exercise transport
    dispatching without slowing the matrix down."""

    async def one_get():
        engine = SnmpEngine()
        error_indication, _es, _ei, _vb = await async_getCmd(
            engine,
            credentials(),
            async_target(),
            ContextData(),
            ObjectType(ObjectIdentity(SYS_UPTIME)),
        )
        return error_indication

    async def main():
        return await asyncio.gather(*(one_get() for _ in range(15)))

    indications = asyncio.run(main())
    failures = [ind for ind in indications if ind is not None]
    assert not failures, f"{len(failures)}/{len(indications)} concurrent GETs failed: {failures}"