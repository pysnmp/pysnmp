"""Diffie-Hellman USM key change against the real Net-SNMP agent (:RFC:`2786`).

Runs in the ``v3-dh`` slot of the matrix in
``.github/workflows/net-snmp-integration.yml``, the one profile whose agent is
built with ``snmp-usm-dh-objects-mib``. The packaged Debian agent the other
profiles run has that module compiled out, so these tests would only ever see
noSuchObject there. Locally (without the env var) the module is skipped.

What makes this worth running against a foreign implementation: a key agreement
implemented from the RFC alone can be perfectly self-consistent and still agree
with nobody. The assertion that settles it is not that the exchange completed,
but that the key *the agent installed* is the key this engine derived -- which
is only observable by authenticating with it afterwards.
"""

import os

import pytest

from pysnmp.hlapi import (
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    dh_key_change,
    get_cmd,
    next_cmd,
    usmHMACSHAAuthProtocol,
    usmKeyTypeLocalized,
)
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.proto.secmod.rfc2786 import (
    OAKLEY_GROUP_2,
    decodeDHParameters,
    keyChangeInstance,
    parseKeyChangeInstance,
    usmDHParameters,
    usmDHUserAuthKeyChange,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("NETSNMP_PROFILE") != "v3-dh",
    reason="The Diffie-Hellman agent only runs in the v3-dh CI profile.",
)

AGENT_HOST = ("127.0.0.1", 1161)
AUTH_PASSPHRASE = "ciAuthPass123"
#: The user the key-change tests rotate.
ROTATED_USER = "ci-dh"
#: The user that keeps its original passphrase, for checks that must not depend
#: on whether a rotation has already happened.
STATIC_USER = "ci-dh-static"
SYS_NAME = "1.3.6.1.2.1.1.5.0"
#: SHA-1 localizes to 20 octets, so that is what the right-most bits of the
#: shared secret have to yield.
SHA1_KEY_LENGTH = 20


def target():
    """A fresh transport target; the sync facade closes the one it is given."""
    return UdpTransportTarget(AGENT_HOST, timeout=2, retries=2)


def passphraseCredentials(userName=ROTATED_USER):
    """The credentials the agent was configured with."""
    return UsmUserData(userName, AUTH_PASSPHRASE, authProtocol=usmHMACSHAAuthProtocol)


def localizedCredentials(result, userName=ROTATED_USER):
    """Credentials built from what a key change returned.

    A localized key is bound to one engine ID and USM will not take it without
    being told which, so the engine ID the exchange learned is as much a part of
    the result as the key.
    """
    return UsmUserData(
        userName,
        result.key,
        authProtocol=usmHMACSHAAuthProtocol,
        authKeyType=usmKeyTypeLocalized,
        securityEngineId=OctetString(result.securityEngineId),
    )


def getSysName(authData):
    """GET sysName.0, returning the raw HLAPI result tuple."""
    return next(
        get_cmd(
            SnmpEngine(),
            authData,
            target(),
            ContextData(),
            ObjectType(ObjectIdentity(SYS_NAME)),
        )
    )


def walkColumn(column, userName=STATIC_USER):
    """Collect the instance OIDs of one column, as the agent hands them out."""
    instances = []
    for errorIndication, errorStatus, _errorIndex, varBinds in next_cmd(
        SnmpEngine(),
        passphraseCredentials(userName),
        target(),
        ContextData(),
        ObjectType(ObjectIdentity(column)),
        lexicographicMode=False,
    ):
        assert errorIndication is None, errorIndication
        assert not errorStatus, errorStatus.prettyPrint()
        instances.append(tuple(varBinds[0][0]))
    return instances


def changeAuthKey(authData):
    """Run one Diffie-Hellman authentication key change."""
    return dh_key_change(SnmpEngine(), authData, target(), ContextData(), "auth")


class TestParameters:
    """What the agent publishes before any agreement happens."""

    def test_agent_publishes_oakley_group_2(self):
        """Net-SNMP hard-codes the group RFC 2409 section 6.2 names."""
        errorIndication, errorStatus, _errorIndex, varBinds = next(
            get_cmd(
                SnmpEngine(),
                passphraseCredentials(STATIC_USER),
                target(),
                ContextData(),
                ObjectType(ObjectIdentity(usmDHParameters + (0,))),
            )
        )

        assert errorIndication is None
        assert not errorStatus

        parameters = decodeDHParameters(varBinds[0][1].asOctets())
        assert parameters == OAKLEY_GROUP_2

    def test_row_index_matches_the_one_this_engine_builds(self):
        """usmDHUserKeyTable is indexed the way keyChangeInstance encodes it.

        Read-only, and independent of the key-change driver: it walks the
        column, takes the index apart the way the agent put it together, and
        checks that feeding those parts back in reproduces the agent's OID. An
        index codec that disagrees would address the wrong row, or none.
        """
        rows = walkColumn(usmDHUserAuthKeyChange)
        assert rows, "the agent published no usmDHUserKeyTable rows"

        users = set()
        for instance in rows:
            engineId, userName = parseKeyChangeInstance(
                usmDHUserAuthKeyChange, instance
            )
            assert (
                keyChangeInstance(usmDHUserAuthKeyChange, engineId, userName)
                == instance
            )
            users.add(userName.decode())

        assert {ROTATED_USER, STATIC_USER} <= users


class TestKeyChange:
    """The exchange itself, end to end against the agent.

    One test, deliberately: a key change invalidates the credentials that ran
    it, so splitting the steps would make each test depend on the order of the
    last. The steps are asserted as they go.
    """

    def test_agent_installs_the_key_this_engine_derived(self):
        """The whole contract of RFC 2786, checked from both ends."""
        # The passphrase works to begin with.
        errorIndication, errorStatus, _errorIndex, varBinds = getSysName(
            passphraseCredentials()
        )
        assert errorIndication is None
        assert not errorStatus
        assert varBinds[0][1].asOctets().decode() == "pysnmp-ci-v3-dh"

        # Agree a new key. Nothing that crosses the wire in this exchange is
        # the key, and the old one was never needed to compute it.
        result = changeAuthKey(passphraseCredentials())
        assert len(result.key) == SHA1_KEY_LENGTH
        assert result.parameters == OAKLEY_GROUP_2

        suffix = (len(ROTATED_USER),) + tuple(ROTATED_USER.encode())
        assert result.instance[-len(suffix) :] == suffix

        # The agent re-keyed on commit, so what authenticated a moment ago no
        # longer does. Without this the next assertion would prove nothing --
        # an agent that ignored the SET would still answer the old passphrase.
        errorIndication, _errorStatus, _errorIndex, _varBinds = getSysName(
            passphraseCredentials()
        )
        assert errorIndication is not None

        # And the key derived here is the key the agent installed.
        errorIndication, errorStatus, _errorIndex, varBinds = getSysName(
            localizedCredentials(result)
        )
        assert errorIndication is None, (
            f"the derived key did not authenticate: {errorIndication}"
        )
        assert not errorStatus
        assert varBinds[0][1].asOctets().decode() == "pysnmp-ci-v3-dh"

        # A second change, run under the derived key, agrees a different key
        # again: the result is ordinary credentials, not a one-shot token.
        second = changeAuthKey(localizedCredentials(result))
        assert second.key != result.key
        assert second.securityEngineId == result.securityEngineId

        errorIndication, errorStatus, _errorIndex, varBinds = getSysName(
            localizedCredentials(second)
        )
        assert errorIndication is None
        assert not errorStatus
        assert varBinds[0][1].asOctets().decode() == "pysnmp-ci-v3-dh"
