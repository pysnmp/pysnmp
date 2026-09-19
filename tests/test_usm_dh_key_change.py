"""The exchange a Diffie-Hellman key change runs, with the agent stubbed out.

tests/test_netsnmp_usm_dh.py proves the exchange interoperates, but it only
runs in one CI profile and only takes the happy path -- an agent will not
produce a malformed index or drop a response on request. What is checked here
is the order of operations and what happens when a step fails, because the SET
is the one step that cannot be undone: everything the result needs has to be
derived before it, or a failure late in the flow leaves the agent re-keyed and
the caller holding nothing that can reach it.

The fake agent also computes the shared secret from its own side, so the key the
driver returns is checked against a peer rather than against itself.
"""

import asyncio

import pytest

from pysnmp.hlapi.asyncio import dh as dh_module
from pysnmp.hlapi.asyncio.dh import DHKeyChangeError, dh_key_change
from pysnmp.hlapi.auth import UsmUserData, usmHMACSHAAuthProtocol
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.proto.secmod.rfc2786 import (
    OAKLEY_GROUP_2,
    buildKeyChangeValue,
    computeSharedSecret,
    deriveKey,
    encodeDHParameters,
    generateKeyPair,
    keyChangeInstance,
    splitKeyChangeValue,
    usmDHUserAuthKeyChange,
)

ENGINE_ID = bytes.fromhex("80001f8880809cf06cd99dad6a00000000")
USER = "ci-dh"
SHA1_KEY_LENGTH = 20


class _ErrorStatus:
    """Truthy, and prints the way an SNMP error status does."""

    def __init__(self, name):
        self._name = name

    def __bool__(self):
        return True

    def prettyPrint(self):
        return self._name


class _FakeAgent:
    """Answers the reads a key change makes, and records the SET.

    Keeps its own private exponent, so that it can complete the agreement from
    the other side exactly as a real agent would.
    """

    def __init__(self, *, parameters=OAKLEY_GROUP_2, setFailure=None):
        self.parameters = parameters
        self.setFailure = setFailure
        self.keyPair = generateKeyPair(parameters)
        self.instance = keyChangeInstance(usmDHUserAuthKeyChange, ENGINE_ID, USER)
        self.setValues = []
        self.setCalls = 0

    async def getCmd(self, _engine, _auth, _target, _context, *_varBinds, **_options):
        """usmDHParameters.0 -- the only GET the flow makes by default."""
        return (
            None,
            0,
            0,
            [
                (
                    (1, 3, 6, 1, 3, 101, 1, 1, 1, 0),
                    OctetString(encodeDHParameters(self.parameters)),
                )
            ],
        )

    async def nextCmd(self, _engine, _auth, _target, _context, *_varBinds, **_options):
        """One row of usmDHUserKeyTable, carrying this agent's public value."""
        return (None, 0, 0, [[(self.instance, OctetString(self.keyPair.public))]])

    async def setCmd(self, _engine, _auth, _target, _context, *_varBinds, **_options):
        """Answer the SET as configured. The value is captured by `keyChangeValue`.

        An unresolved ObjectType will not be indexed -- it needs a MIB view
        first -- so the offered value is recorded where it is built instead.
        """
        self.setCalls += 1
        if self.setFailure is not None:
            return (*self.setFailure, 0, [])
        return (None, 0, 0, [])

    def keyChangeValue(self, peerPublic, ownPublic):
        """Stands in for buildKeyChangeValue, recording what it produced."""
        value = buildKeyChangeValue(peerPublic, ownPublic)
        self.setValues.append(value)
        return value

    def sharedSecret(self, managerPublic):
        """What this agent would install, given the manager's public value."""
        return computeSharedSecret(self.parameters, self.keyPair.private, managerPublic)


@pytest.fixture
def agent(monkeypatch):
    """Put a fake agent behind the three commands the flow issues."""
    fake = _FakeAgent()
    monkeypatch.setattr(dh_module, "getCmd", fake.getCmd)
    monkeypatch.setattr(dh_module, "nextCmd", fake.nextCmd)
    monkeypatch.setattr(dh_module, "setCmd", fake.setCmd)
    monkeypatch.setattr(dh_module, "buildKeyChangeValue", fake.keyChangeValue)
    return fake


def credentials():
    """Credentials whose protocol fixes the derived key at 20 octets."""
    return UsmUserData(USER, "whatever", authProtocol=usmHMACSHAAuthProtocol)


def change(**kwargs):
    """Run one key change against whatever is currently patched in."""
    return asyncio.run(dh_key_change(None, credentials(), None, None, "auth", **kwargs))


class TestAgreementThroughTheFlow:
    """The driver's plumbing, checked against a peer that does the other half."""

    def test_returned_key_is_what_the_agent_would_install(self, agent):
        """The two sides agree, so the halves of the SET value are the right way round."""
        result = change()

        _peerHalf, managerPublic = splitKeyChangeValue(agent.setValues[0])
        expected = deriveKey(agent.sharedSecret(managerPublic), SHA1_KEY_LENGTH)

        assert result.key == expected
        assert len(result.key) == SHA1_KEY_LENGTH

    def test_set_echoes_the_agents_public_value_first(self, agent):
        """The agent rejects the SET with wrongValue if this half does not match."""
        change()
        peerHalf, _managerPublic = splitKeyChangeValue(agent.setValues[0])
        assert peerHalf == agent.keyPair.public

    def test_engine_id_comes_back_from_the_row_index(self, agent):
        """Without it the caller cannot use the localized key it just derived."""
        assert change().securityEngineId == ENGINE_ID


class TestNothingIsSetUntilTheResultIsKnown:
    """The SET is irreversible, so it goes last."""

    def test_unmeetable_key_length_does_not_reach_the_agent(self, agent):
        """A key longer than the shared secret is caught before anything changes."""
        with pytest.raises(DHKeyChangeError) as raised:
            change(keyLength=4096)

        assert agent.setCalls == 0, "the agent was re-keyed for a key we cannot derive"
        assert agent.setValues == [], "a value was built for a SET that must not happen"
        assert raised.value.candidate is None

    def test_zero_key_length_does_not_reach_the_agent(self, agent):
        """Nor does a length that is not a length."""
        with pytest.raises(DHKeyChangeError):
            change(keyLength=0)
        assert agent.setCalls == 0

    def test_unknown_protocol_does_not_reach_the_agent(self, agent):
        """A protocol with no known key length is refused before the SET too."""
        authData = UsmUserData(USER, "whatever", authProtocol=(1, 3, 6, 1, 4, 1, 99))
        with pytest.raises(DHKeyChangeError):
            asyncio.run(dh_key_change(None, authData, None, None, "auth"))
        assert agent.setCalls == 0


class TestFailedSetIsAmbiguous:
    """A SET that fails may still have been applied, so say what might be live."""

    @pytest.mark.parametrize(
        "failure",
        [
            ("No SNMP response received before timeout", 0),
            (None, _ErrorStatus("wrongValue")),
        ],
        ids=["lost-response", "wrongValue-on-retransmission"],
    )
    def test_candidate_key_is_attached(self, monkeypatch, failure):
        """Both shapes of failure can mean the agent re-keyed and we missed it."""
        fake = _FakeAgent(setFailure=failure)
        monkeypatch.setattr(dh_module, "getCmd", fake.getCmd)
        monkeypatch.setattr(dh_module, "nextCmd", fake.nextCmd)
        monkeypatch.setattr(dh_module, "setCmd", fake.setCmd)
        monkeypatch.setattr(dh_module, "buildKeyChangeValue", fake.keyChangeValue)

        with pytest.raises(DHKeyChangeError) as raised:
            change()

        candidate = raised.value.candidate
        assert candidate is not None, "a failed SET left the caller nothing to try"
        assert len(candidate.key) == SHA1_KEY_LENGTH
        assert candidate.securityEngineId == ENGINE_ID

        # And it is the key the agent would have installed, so trying it is
        # actually a way to find out whether the change took effect.
        _peerHalf, managerPublic = splitKeyChangeValue(fake.setValues[0])
        assert candidate.key == deriveKey(
            fake.sharedSecret(managerPublic), SHA1_KEY_LENGTH
        )
