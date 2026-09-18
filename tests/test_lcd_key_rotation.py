"""The hlapi's local configuration datastore, and credentials that change.

`CommandGeneratorLcdConfigurator` caches what it registered so that configuring
the same credentials twice does not write a second set of rows. The cache was
keyed on the user name and security engine ID alone -- which say *which* USM row
is being configured and nothing about what is in it -- so a `UsmUserData`
carrying a new key hit the cache and was silently dropped.
"""

import warnings

import pytest

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.auth import UsmUserData
from pysnmp.hlapi.lcd import CommandGeneratorLcdConfigurator

#: Column 1 of pysnmpUsmKeyEntry is the localized authentication key; column 2
#: is the localized privacy key. These are what the engine actually signs and
#: encrypts with, so they are what a rotation has to have changed.
LOCALIZED_AUTH_KEY = 1
LOCALIZED_PRIV_KEY = 2


class StubTransportTarget:
    """Enough of a transport target for the configurator, without a socket."""

    transportDomain = udp.domainName
    transportAddr = ("127.0.0.1", 161)
    timeout = 100
    retries = 1
    tagList = b""
    iface = None

    def verifyDispatcherCompatibility(self, snmpEngine):
        pass

    def openClientMode(self):
        return udp.UdpTransport().openClientMode()


def localizedKeys(snmpEngine, column):
    """Every localized key in the USM key table, read back off the engine."""
    (entry,) = snmpEngine.getMibBuilder().importSymbols(
        "PYSNMP-USM-MIB", "pysnmpUsmKeyEntry"
    )
    columnOid = tuple(entry.name) + (column,)
    instrum = snmpEngine.msgAndPduDsp.mibInstrumController

    keys = []
    oid = columnOid

    while True:
        ((name, value),) = instrum.readNextVars(((oid, None),))
        if tuple(name[: len(columnOid)]) != columnOid:
            break
        keys.append(bytes(value))
        oid = tuple(name)

    return keys


@pytest.fixture
def configured():
    """Configure a user on a fresh engine, and hand back a way to reconfigure."""
    snmpEngine = SnmpEngine()
    configurator = CommandGeneratorLcdConfigurator()

    def configure(authData):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            configurator.configure(snmpEngine, authData, StubTransportTarget())

        return snmpEngine

    return configure


class TestUsmCredentialsAreReRegistered:
    def test_a_changed_auth_key_reaches_the_engine(self, configured):
        # The reported case: after a usmUserAuthKeyChange, or simply when an
        # application rotates credentials and builds a fresh UsmUserData, the
        # request used to go out signed with the *old* key and the agent
        # answered wrongDigests -- with nothing to say the credentials just
        # passed had been ignored.
        snmpEngine = configured(UsmUserData("u1", "authkey111111", "privkey111111"))
        before = localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)

        configured(UsmUserData("u1", "authkey222222", "privkey111111"))
        after = localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)

        assert before != after

    def test_a_changed_priv_key_reaches_the_engine(self, configured):
        snmpEngine = configured(UsmUserData("u1", "authkey111111", "privkey111111"))
        before = localizedKeys(snmpEngine, LOCALIZED_PRIV_KEY)

        configured(UsmUserData("u1", "authkey111111", "privkey222222"))
        after = localizedKeys(snmpEngine, LOCALIZED_PRIV_KEY)

        assert before != after

    def test_a_changed_auth_protocol_reaches_the_engine(self, configured):
        from pysnmp.hlapi.auth import (
            usmHMAC128SHA224AuthProtocol,
            usmHMACSHAAuthProtocol,
        )

        snmpEngine = configured(
            UsmUserData(
                "u1",
                "authkey111111",
                "privkey111111",
                authProtocol=usmHMACSHAAuthProtocol,
            )
        )
        before = localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)

        configured(
            UsmUserData(
                "u1",
                "authkey111111",
                "privkey111111",
                authProtocol=usmHMAC128SHA224AuthProtocol,
            )
        )
        after = localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)

        assert before != after

    def test_re_registering_replaces_the_row_rather_than_adding_one(self, configured):
        # addV3User() on an existing row is not a replace, so the old row is
        # deleted first. If it were not, the table would grow a second row for
        # the same user and which one the engine picked would be luck.
        snmpEngine = configured(UsmUserData("u1", "authkey111111", "privkey111111"))

        assert len(localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)) == 1

        configured(UsmUserData("u1", "authkey222222", "privkey111111"))

        assert len(localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)) == 1

    def test_identical_credentials_still_register_only_once(self, configured):
        # The cache still has to do its job: repeating a call must not rewrite
        # the row, which is what lets several generators share one engine.
        snmpEngine = configured(UsmUserData("u1", "authkey111111", "privkey111111"))
        first = localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)

        configured(UsmUserData("u1", "authkey111111", "privkey111111"))
        second = localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)

        assert first == second
        assert len(second) == 1

    def test_two_different_users_keep_their_own_rows(self, configured):
        snmpEngine = configured(UsmUserData("u1", "authkey111111", "privkey111111"))
        configured(UsmUserData("u2", "authkey222222", "privkey222222"))

        assert len(localizedKeys(snmpEngine, LOCALIZED_AUTH_KEY)) == 2
