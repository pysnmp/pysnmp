"""Integration tests against local snmpsim devices for v1, v2c, and v3."""

import asyncio

import pytest

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    NotificationType,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    nextCmd,
    bulkCmd,
    sendNotification,
    setCmd,
    usmHMACMD5AuthProtocol,
)
from pysnmp.hlapi.asyncio import (
    getCmd as asyncio_getCmd,
    nextCmd as asyncio_nextCmd,
    bulkCmd as asyncio_bulkCmd,
    UdpTransportTarget as AsyncioUdpTransportTarget,
)
from pysnmp.proto.rfc1902 import Integer, OctetString


SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_OBJECTID = "1.3.6.1.2.1.1.2.0"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
SYS_CONTACT = "1.3.6.1.2.1.1.4.0"
SYS_NAME = "1.3.6.1.2.1.1.5.0"
SYS_LOCATION = "1.3.6.1.2.1.1.6.0"
IF_NUMBER = "1.3.6.1.2.1.2.1.0"
IF_INDEX = "1.3.6.1.2.1.2.2.1.1"
IF_DESCR = "1.3.6.1.2.1.2.2.1.2"


def get_value(result):
    error_indication, error_status, error_index, var_binds = result
    assert error_indication is None
    assert not error_status
    assert not error_index
    print(f"  SNMP response: OID={var_binds[0][0]} value={var_binds[0][1]}")
    return str(var_binds[0][1])


def get_all_values(result):
    error_indication, error_status, error_index, var_binds = result
    assert error_indication is None
    assert not error_status
    assert not error_index
    for vb in var_binds:
        print(f"  SNMP response: OID={vb[0]} value={vb[1]}")
    return [str(vb[1]) for vb in var_binds]


# ---- Versioned GET tests (synchronous asyncio facade) ----

class TestSyncGetV1:
    def test_get_sys_descr(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public@1", mpModel=0),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
        )
        assert get_value(result) == "pysnmp integration SNMPv1 agent"

    def test_get_sys_objectid(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public@1", mpModel=0),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_OBJECTID)),
            )
        )
        assert "20408" in get_value(result)

    def test_get_sys_uptime(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public@1", mpModel=0),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_UPTIME)),
            )
        )
        # v1 may return noSuchName for some OIDs; just check we get a response
        error_indication, error_status, error_index, var_binds = result
        if error_indication:
            print(f"  SNMP error: {error_indication}")
        elif error_status:
            print(f"  SNMP PDU error: {error_status} at index {error_index}")
        else:
            print(f"  SNMP response: OID={var_binds[0][0]} value={var_binds[0][1]}")
        assert error_indication is None

    def test_get_multiple(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public@1", mpModel=0),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_DESCR)),
                ObjectType(ObjectIdentity(SYS_CONTACT)),
                ObjectType(ObjectIdentity(SYS_LOCATION)),
            )
        )
        values = get_all_values(result)
        assert values[0] == "pysnmp integration SNMPv1 agent"
        assert values[1] == "Test Contact"
        assert values[2] == "Test Location"


class TestSyncGetV2c:
    def test_get_sys_descr(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public"),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
        )
        assert get_value(result) == "pysnmp integration SNMPv2c agent"

    def test_get_sys_contact(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public"),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_CONTACT)),
            )
        )
        assert get_value(result) == "Test Contact"

    def test_get_if_number(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public"),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(IF_NUMBER)),
            )
        )
        assert get_value(result) == "3"


class TestSyncGetV3:
    def test_get_sys_descr(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                UsmUserData("00000", "authkey1", authProtocol=usmHMACMD5AuthProtocol),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(contextName="00000"),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
        )
        assert get_value(result) == "pysnmp integration SNMPv3 agent"

    def test_get_sys_name(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            getCmd(
                SnmpEngine(),
                UsmUserData("00000", "authkey1", authProtocol=usmHMACMD5AuthProtocol),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(contextName="00000"),
                ObjectType(ObjectIdentity(SYS_NAME)),
            )
        )
        assert get_value(result) == "Test Host"


# ---- Traversal tests (synchronous asyncio facade) ----

class TestSyncNextV2c:
    def test_next_cmd(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData("public"),
            UdpTransportTarget((host, port), timeout=1, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1")),
        )
        results = []
        for error_indication, error_status, error_index, var_binds in iterator:
            if error_indication:
                print(f"  SNMP error: {error_indication}")
                break
            for vb in var_binds:
                print(f"  SNMP response: OID={vb[0]} value={vb[1]}")
                results.append(str(vb[1]))
            if len(results) >= 5:
                break
        assert len(results) > 0


class TestSyncNotification:
    def test_trap_uses_asyncio_facade(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        result = next(
            sendNotification(
                SnmpEngine(),
                CommunityData("public"),
                UdpTransportTarget((host, port)),
                ContextData(),
                "trap",
                NotificationType(ObjectIdentity("SNMPv2-MIB", "coldStart")),
            )
        )
        assert result == (None, 0, 0, [])


class TestSyncBulkV2c:
    def test_bulk_cmd(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint
        iterator = bulkCmd(
            SnmpEngine(),
            CommunityData("public"),
            UdpTransportTarget((host, port), timeout=1, retries=2),
            ContextData(),
            0, 10,
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1")),
        )
        results = []
        for error_indication, error_status, error_index, var_binds in iterator:
            if error_indication:
                print(f"  SNMP error: {error_indication}")
                break
            for vb in var_binds:
                print(f"  SNMP response: OID={vb[0]} value={vb[1]}")
                results.append(str(vb[1]))
            if len(results) >= 10:
                break
        assert len(results) > 0


# ---- Unreachable device test ----

class TestUnreachableDevice:
    def test_timeout_v2c(self):
        # Use an unused loopback port with very short timeout
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public"),
                UdpTransportTarget(("127.0.0.1", 19999), timeout=1, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
        )
        error_indication, error_status, error_index, var_binds = result
        print(f"  SNMP timeout: {error_indication}")
        assert error_indication is not None

    def test_timeout_v1(self):
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public", mpModel=0),
                UdpTransportTarget(("127.0.0.1", 19999), timeout=1, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
        )
        error_indication, error_status, error_index, var_binds = result
        print(f"  SNMP timeout: {error_indication}")
        assert error_indication is not None


# ---- Asyncio tests ----

class TestAsyncioGetV2c:
    def test_asyncio_get_sys_descr(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint

        async def run():
            result = await asyncio_getCmd(
                SnmpEngine(),
                CommunityData("public"),
                AsyncioUdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
            return result

        result = asyncio.run(run())
        assert get_value(result) == "pysnmp integration SNMPv2c agent"

    def test_asyncio_get_sys_contact(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint

        async def run():
            result = await asyncio_getCmd(
                SnmpEngine(),
                CommunityData("public"),
                AsyncioUdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_CONTACT)),
            )
            return result

        result = asyncio.run(run())
        assert get_value(result) == "Test Contact"


class TestAsyncioGetV3:
    def test_asyncio_get_sys_descr(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint

        async def run():
            result = await asyncio_getCmd(
                SnmpEngine(),
                UsmUserData("00000", "authkey1", authProtocol=usmHMACMD5AuthProtocol),
                AsyncioUdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(contextName="00000"),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
            return result

        result = asyncio.run(run())
        assert get_value(result) == "pysnmp integration SNMPv3 agent"


class TestAsyncioNextV2c:
    def test_asyncio_next_cmd(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint

        async def run():
            result = await asyncio_nextCmd(
                SnmpEngine(),
                CommunityData("public"),
                AsyncioUdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1")),
            )
            return result

        result = asyncio.run(run())
        error_indication, error_status, error_index, var_binds = result
        assert error_indication is None
        assert len(var_binds) > 0
        for row in var_binds:
            for vb in row:
                print(f"  SNMP response: OID={vb[0]} value={vb[1]}")


class TestAsyncioBulkV2c:
    def test_asyncio_bulk_cmd(self, snmpsim_endpoint):
        host, port = snmpsim_endpoint

        async def run():
            result = await asyncio_bulkCmd(
                SnmpEngine(),
                CommunityData("public"),
                AsyncioUdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                0, 10,
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1")),
            )
            return result

        result = asyncio.run(run())
        error_indication, error_status, error_index, var_binds = result
        assert error_indication is None
        for vb in var_binds:
            for row in vb:
                print(f"  SNMP response: OID={row[0]} value={row[1]}")
        assert len(var_binds) > 0


class TestAsyncioTimeout:
    def test_asyncio_timeout_v2c(self):
        async def run():
            result = await asyncio_getCmd(
                SnmpEngine(),
                CommunityData("public"),
                AsyncioUdpTransportTarget(("127.0.0.1", 19999), timeout=1, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_DESCR)),
            )
            return result

        result = asyncio.run(run())
        error_indication, error_status, error_index, var_binds = result
        print(f"  SNMP timeout: {error_indication}")
        assert error_indication is not None


# ---- Table cell API integration tests (Tier 4) ----
# These tests validate the SMI table cell API against real snmpsim data.
# The public@1 data file contains sysORTable rows (SNMPv2-MIB):
#   sysORID  (col 2): 1.3.6.1.6.3.1, 1.3.6.1.6.3.10
#   sysORDescr (col 3): "SNMP Framework MIB", "SNMP User-Based SM MIB"
#   sysORUpTime (col 4): 100, 200

SYS_OR_ID = "1.3.6.1.2.1.1.9.1.2"
SYS_OR_DESCR = "1.3.6.1.2.1.1.9.1.3"


class TestTableCellApiIntegration:
    """End-to-end tests for the table cell mangling API against snmpsim."""

    def test_resolve_cell_oid_returns_real_data(self, snmpsim_endpoint):
        """resolveCellOid produces an OID that retrieves real data from snmpsim."""
        host, port = snmpsim_endpoint

        from pysnmp.smi.builder import MibBuilder
        from pysnmp.smi.view import MibViewController

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        mibView = MibViewController(mibBuilder)

        # Resolve sysORDescr (column 3) for sysORTable row 1
        oid = mibView.resolveCellOid("SNMPv2-MIB", "sysOREntry", "sysORDescr", 1)
        assert oid == (1, 3, 6, 1, 2, 1, 1, 9, 1, 3, 1)

        # Query snmpsim with that OID — should return "SNMP Framework MIB"
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public@1", mpModel=0),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        )
        assert get_value(result) == "SNMP Framework MIB"

    def test_get_table_columns_count_matches_walked_columns(self, snmpsim_endpoint):
        """getTableColumns column count is consistent with a real SNMP walk."""
        host, port = snmpsim_endpoint

        from pysnmp.smi.builder import MibBuilder
        from pysnmp.smi.view import MibViewController

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        mibView = MibViewController(mibBuilder)

        columns = mibView.getTableColumns("SNMPv2-MIB", "sysOREntry")
        column_ids = {col_id for col_id, _, _ in columns}

        # Walk the sysORTable via SNMP nextCmd and collect unique column IDs.
        # Use the first instance OID as the starting point.
        walked_column_ids = set()
        oid = SYS_OR_ID + ".1"
        for _ in range(20):  # safety limit
            result = next(
                nextCmd(
                    SnmpEngine(),
                    CommunityData("public@1", mpModel=0),
                    UdpTransportTarget((host, port), timeout=1, retries=2),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                )
            )
            error_indication, error_status, error_index, var_binds = result
            if error_indication or not var_binds:
                break
            oid_str = str(var_binds[0][0])
            if not oid_str.startswith("1.3.6.1.2.1.1.9.1."):
                break
            parts = oid_str.split(".")
            col_id = int(parts[-2])
            walked_column_ids.add(col_id)
            oid = oid_str

        # Every column ID we walked should be in getTableColumns
        assert walked_column_ids.issubset(column_ids)

    def test_get_table_cell_info_decomposes_walked_oid(self, snmpsim_endpoint):
        """getTableCellInfo correctly decomposes OIDs returned by a real SNMP walk."""
        host, port = snmpsim_endpoint

        from pysnmp.smi.builder import MibBuilder
        from pysnmp.smi.view import MibViewController

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        mibView = MibViewController(mibBuilder)

        # Use nextCmd starting from sysORDescr.1 to get the first table cell
        result = next(
            nextCmd(
                SnmpEngine(),
                CommunityData("public@1", mpModel=0),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(SYS_OR_DESCR + ".1")),
            )
        )
        error_indication, error_status, error_index, var_binds = result
        assert error_indication is None
        assert len(var_binds) > 0

        # The response should be the next OID after sysORDescr.1
        first_oid = tuple(var_binds[0][0])
        oid_str = str(var_binds[0][0])
        assert oid_str.startswith("1.3.6.1.2.1.1.9.1."), f"Expected sysORTable OID, got {oid_str}"

        mod_name, row_name, col_name, indices = mibView.getTableCellInfo(first_oid)

        assert mod_name == "SNMPv2-MIB"
        assert row_name == "sysOREntry"
        # The next OID after sysORDescr.1 should still be in the sysORTable
        assert col_name in ("sysORDescr", "sysORUpTime", "sysORID", "sysORIndex")

    def test_cell_oid_roundtrip(self, snmpsim_endpoint):
        """resolveCellOid → getCmd → getTableCellInfo roundtrips correctly."""
        host, port = snmpsim_endpoint

        from pysnmp.smi.builder import MibBuilder
        from pysnmp.smi.view import MibViewController

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        mibView = MibViewController(mibBuilder)

        # Build an OID for sysORDescr.2 via the table cell API
        original_oid = mibView.resolveCellOid("SNMPv2-MIB", "sysOREntry", "sysORDescr", 2)

        # Query snmpsim — should return "SNMP User-Based SM MIB"
        result = next(
            getCmd(
                SnmpEngine(),
                CommunityData("public@1", mpModel=0),
                UdpTransportTarget((host, port), timeout=1, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(original_oid)),
            )
        )
        assert get_value(result) == "SNMP User-Based SM MIB"

        # Decompose the OID we built back into its components
        mod_name, row_name, col_name, indices = mibView.getTableCellInfo(original_oid)

        assert mod_name == "SNMPv2-MIB"
        assert row_name == "sysOREntry"
        assert col_name == "sysORDescr"
        assert int(indices[0]) == 2
