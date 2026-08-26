"""End-to-end tests against a local snmpsim agent."""

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    usmHMACMD5AuthProtocol,
)


SYS_DESCR = "1.3.6.1.2.1.1.1.0"


def get_value(result):
    error_indication, error_status, error_index, var_binds = result
    assert error_indication is None
    assert not error_status
    assert not error_index
    return str(var_binds[0][1])


def test_snmpsim_v1(snmpsim_endpoint):
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


def test_snmpsim_v2c(snmpsim_endpoint):
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


def test_snmpsim_v3_uses_context_named_data_file(snmpsim_endpoint):
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
