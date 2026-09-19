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
import secrets
import time

import pytest

from pysnmp.hlapi.asyncio import dh as dh_module
from pysnmp.hlapi.asyncio.dh import DHKeyChangeError, dh_key_change
from pysnmp.hlapi.auth import UsmUserData, usmHMACSHAAuthProtocol
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.proto.secmod.rfc2786 import (
    OAKLEY_GROUP_2,
    DHKeyPair,
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

    async def get_cmd(self, _engine, _auth, _target, _context, *_varBinds, **_options):
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

    async def next_cmd(self, _engine, _auth, _target, _context, *_varBinds, **_options):
        """One row of usmDHUserKeyTable, carrying this agent's public value."""
        return (None, 0, 0, [[(self.instance, OctetString(self.keyPair.public))]])

    async def set_cmd(self, _engine, _auth, _target, _context, *_varBinds, **_options):
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
    monkeypatch.setattr(dh_module, "get_cmd", fake.get_cmd)
    monkeypatch.setattr(dh_module, "next_cmd", fake.next_cmd)
    monkeypatch.setattr(dh_module, "set_cmd", fake.set_cmd)
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
        monkeypatch.setattr(dh_module, "get_cmd", fake.get_cmd)
        monkeypatch.setattr(dh_module, "next_cmd", fake.next_cmd)
        monkeypatch.setattr(dh_module, "set_cmd", fake.set_cmd)
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


def _longPair():
    """A pair whose public value occupies the prime's full width."""
    return DHKeyPair(private=2, public=b"\x01" * 128)


def _fittingPair(width):
    """A pair whose public value is narrow enough for `width`."""
    return DHKeyPair(private=3, public=b"\x02" * width)


class TestDrawingAPublicValueThatFits:
    """The agent splits the value down the middle, so our half cannot be wider.

    A public value encodes short only when its leading octet comes out zero,
    about one draw in 256. So when the agent's own value came out short, ours
    has to come out short too: the redraw is *waiting for* that one-in-256
    event, not escaping it. The bound was 8 on the opposite reading, which
    cleared it 3% of the time.
    """

    def test_a_first_draw_that_fits_is_the_only_draw(self, monkeypatch):
        drawn = []

        def generate(_parameters):
            drawn.append(1)
            return _longPair()

        monkeypatch.setattr(dh_module, "generateKeyPair", generate)

        pair = dh_module._drawKeyPairFitting(OAKLEY_GROUP_2, 128)

        assert len(drawn) == 1  # the ordinary case costs nothing
        assert pair.public == _longPair().public

    def test_it_keeps_drawing_past_the_old_bound(self, monkeypatch):
        # 500 is far beyond the 8 draws the bound used to allow and far below
        # the 2048 it allows now, so this passes only because it was raised.
        drawn = []

        def generate(_parameters):
            drawn.append(1)
            return _longPair() if len(drawn) <= 500 else _fittingPair(127)

        monkeypatch.setattr(dh_module, "generateKeyPair", generate)

        pair = dh_module._drawKeyPairFitting(OAKLEY_GROUP_2, 127)

        assert len(drawn) == 501
        assert len(pair.public) == 127

    def test_it_gives_up_after_the_bound_rather_than_spinning(self, monkeypatch):
        drawn = []

        def generate(_parameters):
            drawn.append(1)
            return _longPair()

        monkeypatch.setattr(dh_module, "generateKeyPair", generate)

        with pytest.raises(DHKeyChangeError, match="fits the agent's half"):
            dh_module._drawKeyPairFitting(OAKLEY_GROUP_2, 127)

        assert len(drawn) == dh_module._PUBLIC_VALUE_ATTEMPTS


class TestTheSearchStaysOffTheEventLoop:
    """A draw is a modular exponentiation, and the search can need hundreds.

    Run inline that stalls every other task on the loop for as long as it
    takes, which at the bound the driver now allows is measured in seconds. It
    goes to an executor instead, so the loop keeps serving everything else.
    """

    def test_a_concurrent_task_makes_progress_during_the_search(
        self, agent, monkeypatch
    ):
        async def run():
            ticks = 0
            stop = asyncio.Event()

            async def count():
                nonlocal ticks
                while not stop.is_set():
                    ticks += 1
                    await asyncio.sleep(0.01)

            real = dh_module.generateKeyPair

            def slow(parameters):
                time.sleep(0.15)
                return real(parameters)

            monkeypatch.setattr(dh_module, "generateKeyPair", slow)

            counter = asyncio.create_task(count())
            await asyncio.sleep(0.02)  # let it get going

            await dh_key_change(None, credentials(), None, None, "auth")

            stop.set()
            await counter

            # A stalled loop manages only the two or three ticks from
            # before the search started; a healthy one gets roughly fifteen
            # more. The floor sits far below that, so a loaded CI runner
            # cannot fail this on timing alone.
            assert ticks > 6

        asyncio.run(run())


def _shortKeyPair(parameters, width):
    """A real key pair whose public value encodes to `width` octets.

    Stands in for an agent whose own public value came out with a zero leading
    octet. Stepping `g^x -> g^(x+1)` by multiplication rather than redrawing
    keeps it cheap: the search is the same one-in-256 event the driver faces,
    and a few hundred modular exponentiations would make the test slow enough
    to notice. Sound here because nothing about this pair has to be
    unpredictable -- it only has to be one the agreement works with.
    """
    private = 2 + secrets.randbelow(parameters.prime - 3)
    public = pow(parameters.base, private, parameters.prime)

    while (public.bit_length() + 7) // 8 > width:
        public = public * parameters.base % parameters.prime
        private += 1

    return DHKeyPair(private=private, public=public.to_bytes(width, "big"))


class TestAnAgentWhosePublicValueCameOutShort:
    """The case that failed in CI: the agent's half is 127 octets, not 128."""

    def test_the_key_change_still_agrees(self, monkeypatch):
        fake = _FakeAgent()
        fake.keyPair = _shortKeyPair(fake.parameters, 127)
        monkeypatch.setattr(dh_module, "getCmd", fake.getCmd)
        monkeypatch.setattr(dh_module, "nextCmd", fake.nextCmd)
        monkeypatch.setattr(dh_module, "setCmd", fake.setCmd)
        monkeypatch.setattr(dh_module, "buildKeyChangeValue", fake.keyChangeValue)

        result = change()

        peerPublic, ownPublic = splitKeyChangeValue(fake.setValues[0])

        # Both halves at the agent's width, and the first one is what it
        # published -- anything else is a wrongValue.
        assert len(peerPublic) == 127
        assert len(ownPublic) == 127
        assert peerPublic == fake.keyPair.public

        # And the key really is the one the agent would install.
        assert result.key == deriveKey(fake.sharedSecret(ownPublic), SHA1_KEY_LENGTH)
