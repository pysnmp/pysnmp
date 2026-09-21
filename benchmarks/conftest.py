#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Shared fixtures for the pysnmp benchmark suite."""

import pytest
from payloads import IF_TABLE_OIDS, SYSTEM_OIDS, make_request, make_response
from pyasn1.codec.ber import encoder

from pysnmp.proto import api


@pytest.fixture(scope="session")
def v1_request_substrate():
    return encoder.encode(make_request(api.protoVersion1, SYSTEM_OIDS))


@pytest.fixture(scope="session")
def v2c_request_substrate():
    return encoder.encode(make_request(api.protoVersion2c, SYSTEM_OIDS))


@pytest.fixture(scope="session")
def v2c_response_substrate():
    return encoder.encode(make_response(api.protoVersion2c, IF_TABLE_OIDS))


@pytest.fixture(scope="session")
def mib_builder():
    from pysnmp.smi import builder

    mibBuilder = builder.MibBuilder()
    mibBuilder.loadModules(
        "SNMPv2-MIB",
        "SNMP-FRAMEWORK-MIB",
        "SNMP-TARGET-MIB",
        "SNMP-USER-BASED-SM-MIB",
        "SNMP-VIEW-BASED-ACM-MIB",
    )
    return mibBuilder


@pytest.fixture(scope="session")
def mib_view_controller(mib_builder):
    from pysnmp.smi import view

    return view.MibViewController(mib_builder)


@pytest.fixture(scope="session")
def mib_instrum_controller():
    from pysnmp.smi import builder, instrum

    mibBuilder = builder.MibBuilder()
    mibBuilder.loadModules("SNMPv2-MIB", "__SNMPv2-MIB")
    return instrum.MibInstrumController(mibBuilder)
