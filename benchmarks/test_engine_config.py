#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Benchmarks for SNMP engine construction and credential setup.

These are the one-off costs every pysnmp application pays at start-up,
and they are heavy enough to matter for short-lived processes such as
polling scripts and serverless collectors.
"""

import pytest

from pysnmp.entity import config, engine
from pysnmp.hlapi import (
    CommunityData,
    UsmUserData,
    usmDESPrivProtocol,
    usmHMACMD5AuthProtocol,
)


def test_snmp_engine_bootstrap(benchmark):
    """Instantiating SnmpEngine loads and indexes the core MIB modules."""
    benchmark(engine.SnmpEngine)


@pytest.fixture(scope="module")
def snmp_engine():
    return engine.SnmpEngine()


def test_add_v1_community(benchmark, snmp_engine):
    benchmark(config.addV1System, snmp_engine, "my-area", "public")


def test_add_v3_user_md5_des(benchmark, snmp_engine):
    """Adding a USM user derives and localizes both the auth and priv keys."""
    benchmark(
        config.addV3User,
        snmp_engine,
        "usr-md5-des",
        usmHMACMD5AuthProtocol,
        "authkey1",
        usmDESPrivProtocol,
        "privkey1",
    )


def test_community_data_credentials(benchmark):
    benchmark(CommunityData, "public", mpModel=1)


def test_usm_user_data_credentials(benchmark):
    """UsmUserData hashes the passphrases into keys up front."""
    benchmark(
        UsmUserData,
        "usr-md5-des",
        "authkey1",
        "privkey1",
        authProtocol=usmHMACMD5AuthProtocol,
        privProtocol=usmDESPrivProtocol,
    )
