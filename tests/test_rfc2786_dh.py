"""Diffie-Hellman USM key management arithmetic and encodings (:RFC:`2786`).

The DHKeyChange convention is easy to implement in a way that agrees with
itself and with nothing else, so the vectors here are taken from a real agent
wherever one can supply them: `NETSNMP_USM_DH_PARAMETERS` is the byte-for-byte
value a Net-SNMP 5.9.4 agent returns for usmDHParameters.0, and the index
encoding is the one its `snmpusm` builds.

The interop half -- that an agent installs the key this module derives -- is in
tests/test_netsnmp_usm_dh.py, which needs the agent itself.
"""

import subprocess
import sys

import pytest

from pysnmp.proto.secmod.rfc2786 import (
    OAKLEY_GROUP_1,
    OAKLEY_GROUP_2,
    DHParameters,
    buildKeyChangeValue,
    computeSharedSecret,
    decodeDHParameters,
    deriveKey,
    deriveKickstartKeys,
    encodeDHParameters,
    generateKeyPair,
    keyChangeInstance,
    parseKeyChangeInstance,
    splitKeyChangeValue,
    usmDHUserAuthKeyChange,
    usmDHUserPrivKeyChange,
)

#: usmDHParameters.0 exactly as Net-SNMP 5.9.4 publishes it: a PKCS#3
#: DHParameter holding Oakley Group 2 with a base of 2 and no private-value
#: length.
NETSNMP_USM_DH_PARAMETERS = bytes.fromhex(
    "308187028181"
    "00"
    "ffffffffffffffffc90fdaa22168c234c4c6628b80dc1cd1"
    "29024e088a67cc74020bbea63b139b22514a08798e3404dd"
    "ef9519b3cd3a431b302b0a6df25f14374fe1356d6d51c245"
    "e485b576625e7ec6f44c42e9a637ed6b0bff5cb6f406b7ed"
    "ee386bfb5a899fa5ae9f24117c4b1fe649286651ece65381"
    "ffffffffffffffff"
    "020102"
)


class TestParameters:
    """usmDHParameters, which is a PKCS#3 DHParameter in an OCTET STRING."""

    def test_netsnmp_parameters_decode_to_oakley_group_2(self):
        """What a real agent publishes is the group RFC 2409 section 6.2 names."""
        assert decodeDHParameters(NETSNMP_USM_DH_PARAMETERS) == OAKLEY_GROUP_2

    def test_decode_is_exact_round_trip(self):
        """Re-encoding an agent's parameters reproduces its octets."""
        parameters = decodeDHParameters(NETSNMP_USM_DH_PARAMETERS)
        assert encodeDHParameters(parameters) == NETSNMP_USM_DH_PARAMETERS

    def test_prime_length_is_the_secret_width(self):
        """Oakley Group 2 is 1024 bits, so a shared secret is 128 octets."""
        assert OAKLEY_GROUP_2.primeLength == 128
        assert OAKLEY_GROUP_1.primeLength == 96

    def test_optional_private_value_length_round_trips(self):
        """The third component is OPTIONAL and survives a round trip when set."""
        parameters = DHParameters(
            prime=OAKLEY_GROUP_2.prime, base=2, privateValueLength=160
        )
        assert decodeDHParameters(encodeDHParameters(parameters)) == parameters

    def test_absent_private_value_length_is_none(self):
        """An absent OPTIONAL component decodes to None, not to a schema object."""
        assert decodeDHParameters(NETSNMP_USM_DH_PARAMETERS).privateValueLength is None

    @pytest.mark.parametrize(
        "substrate,reason",
        [
            (b"", "empty"),
            (b"\x04\x01\x00", "not a SEQUENCE"),
            (NETSNMP_USM_DH_PARAMETERS + b"\x00", "trailing octets"),
        ],
    )
    def test_malformed_parameters_are_refused(self, substrate, reason):
        """Anything that is not one DHParameter raises rather than half-decoding."""
        with pytest.raises(ValueError):
            decodeDHParameters(substrate)

    @pytest.mark.parametrize(
        "parameters",
        [
            DHParameters(prime=2, base=2),
            # p = 3 leaves only 0 and 1 to draw an exponent from, so a
            # reject-and-redraw generator never terminates on it. Refused here
            # rather than hanging later on parameters the agent chose.
            DHParameters(prime=3, base=2),
            DHParameters(prime=OAKLEY_GROUP_2.prime, base=1),
            DHParameters(prime=OAKLEY_GROUP_2.prime, base=OAKLEY_GROUP_2.prime),
        ],
    )
    def test_degenerate_parameters_are_refused(self, parameters):
        """A prime or base no agreement could use is rejected at decode."""
        with pytest.raises(ValueError):
            decodeDHParameters(encodeDHParameters(parameters))


class TestAgreement:
    """Generating a key pair and completing the agreement."""

    def test_both_sides_reach_the_same_secret(self):
        """The whole point: two independent draws agree."""
        manager = generateKeyPair(OAKLEY_GROUP_2)
        agent = generateKeyPair(OAKLEY_GROUP_2)

        assert computeSharedSecret(
            OAKLEY_GROUP_2, manager.private, agent.public
        ) == computeSharedSecret(OAKLEY_GROUP_2, agent.private, manager.public)

    def test_public_value_matches_the_private_exponent(self):
        """The published value really is g^x mod p."""
        keyPair = generateKeyPair(OAKLEY_GROUP_2)
        expected = pow(OAKLEY_GROUP_2.base, keyPair.private, OAKLEY_GROUP_2.prime)
        assert int.from_bytes(keyPair.public, "big") == expected

    def test_public_value_has_no_leading_zero(self):
        """DHKeyChange requires the minimal encoding, whose first octet is non-zero."""
        for _ in range(16):
            assert generateKeyPair(OAKLEY_GROUP_2).public[0] != 0

    def test_private_exponent_is_not_degenerate(self):
        """An exponent of 0 or 1 would publish 1 or g and give away the secret."""
        for _ in range(16):
            assert generateKeyPair(OAKLEY_GROUP_2).private > 1

    @pytest.mark.parametrize("prime", [2, 3])
    def test_key_generation_refuses_a_prime_with_nothing_to_draw(self, prime):
        """Also guarded in the generator, for parameters not built by decoding."""
        with pytest.raises(ValueError):
            generateKeyPair(DHParameters(prime=prime, base=2))

    def test_key_generation_terminates_on_small_primes(self):
        """One draw, no rejection loop: small primes return instead of spinning.

        The parameters come from the agent, so any loop conditioned on them is a
        loop the agent controls.
        """
        for prime in (5, 7, 11, 13):
            keyPair = generateKeyPair(DHParameters(prime=prime, base=2))
            assert 2 <= keyPair.private <= prime - 2

    def test_exponent_stays_in_the_usable_interval(self):
        """0, 1 and p-1 are excluded; the rest of [2, p-2] is fair game."""
        for _ in range(64):
            private = generateKeyPair(OAKLEY_GROUP_2).private
            assert 2 <= private <= OAKLEY_GROUP_2.prime - 2

    def test_private_value_length_bounds_the_exponent(self):
        """When the parameters carry l, the exponent comes from [2^(l-1), 2^l)."""
        parameters = DHParameters(
            prime=OAKLEY_GROUP_2.prime, base=2, privateValueLength=64
        )
        for _ in range(16):
            assert generateKeyPair(parameters).private.bit_length() == 64

    def test_shared_secret_is_the_full_prime_width(self):
        """The secret is left-padded, because the key is counted from its right."""
        manager = generateKeyPair(OAKLEY_GROUP_2)
        agent = generateKeyPair(OAKLEY_GROUP_2)
        secret = computeSharedSecret(OAKLEY_GROUP_2, manager.private, agent.public)
        assert len(secret) == OAKLEY_GROUP_2.primeLength

    @pytest.mark.parametrize("peer", [b"\x00", b"\x01", b""])
    def test_peer_public_value_out_of_group_is_refused(self, peer):
        """0, 1 and p-1 are the values that would leak the exponent."""
        with pytest.raises(ValueError):
            computeSharedSecret(OAKLEY_GROUP_2, 12345, peer)

    def test_peer_public_value_above_the_prime_is_refused(self):
        """A value at or above p-1 is not a public value from this group."""
        with pytest.raises(ValueError):
            computeSharedSecret(
                OAKLEY_GROUP_2,
                12345,
                OAKLEY_GROUP_2.prime.to_bytes(OAKLEY_GROUP_2.primeLength, "big"),
            )


class TestKeyDerivation:
    """Mapping a shared secret onto an operational key."""

    def test_key_is_the_right_most_octets(self):
        """Every DHKeyChange object maps sk the same way: right-most n bits."""
        secret = bytes(range(128))
        assert deriveKey(secret, 20) == secret[-20:]
        assert deriveKey(secret, 16) == secret[-16:]

    def test_key_longer_than_the_secret_is_refused(self):
        """A 20-octet key cannot come out of a 16-octet secret."""
        with pytest.raises(ValueError):
            deriveKey(bytes(16), 20)

    @pytest.mark.parametrize("length", [0, -1])
    def test_non_length_is_refused(self, length):
        """Zero and negative lengths are programming errors, not empty keys."""
        with pytest.raises(ValueError):
            deriveKey(bytes(128), length)

    def test_kickstart_keys_are_pinned(self):
        """Kickstart runs PBKDF2 with the salts and count the MIB fixes.

        Pinned so that a change to either salt, the iteration count or the PRF
        has to be deliberate: they are the interoperability contract, not
        tuning knobs.
        """
        authKey, privKey = deriveKickstartKeys(bytes(range(1, 33)))
        assert authKey.hex() == "2d61a7dadf07a3d0a0c8858d981e0170"
        assert privKey.hex() == "1d0f46c19d1fd421384d314239eae7fe"

    def test_kickstart_keys_differ_from_each_other(self):
        """The two salts exist so one secret yields two independent keys."""
        authKey, privKey = deriveKickstartKeys(bytes(range(1, 33)))
        assert authKey != privKey

    def test_kickstart_key_lengths_are_configurable(self):
        """The MIB's defaults are MD5 and DES, but the derivation is not."""
        authKey, privKey = deriveKickstartKeys(
            bytes(32), authKeyLength=20, privKeyLength=32
        )
        assert (len(authKey), len(privKey)) == (20, 32)


class TestKeyChangeValue:
    """The octet string a DHKeyChange object is SET to."""

    def test_value_is_the_two_public_values(self):
        """Agent's value first, then ours -- the agent checks the first half."""
        assert buildKeyChangeValue(b"\x11\x22", b"\x33\x44") == b"\x11\x22\x33\x44"

    def test_short_own_value_is_left_padded(self):
        """The agent splits down the middle, so both halves must be one width."""
        value = buildKeyChangeValue(b"\xaa\xbb\xcc", b"\x01")
        assert value == b"\xaa\xbb\xcc\x00\x00\x01"

    def test_longer_own_value_is_refused(self):
        """It cannot be padded to fit, so the caller must draw another pair."""
        with pytest.raises(ValueError):
            buildKeyChangeValue(b"\x01", b"\x02\x03")

    def test_empty_peer_value_is_refused(self):
        """An agent that published nothing has nothing to agree with."""
        with pytest.raises(ValueError):
            buildKeyChangeValue(b"", b"\x01")

    def test_split_reverses_build(self):
        """What the agent does to the value we build."""
        manager = generateKeyPair(OAKLEY_GROUP_2)
        agent = generateKeyPair(OAKLEY_GROUP_2)
        value = buildKeyChangeValue(agent.public, manager.public)

        peerHalf, ownHalf = splitKeyChangeValue(value)
        assert peerHalf == agent.public
        assert int.from_bytes(ownHalf, "big") == int.from_bytes(manager.public, "big")

    @pytest.mark.parametrize("value", [b"", b"\x01\x02\x03"])
    def test_odd_or_empty_value_does_not_split(self, value):
        """Neither can be two halves of equal width."""
        with pytest.raises(ValueError):
            splitKeyChangeValue(value)


class TestRowIndex:
    """Addressing a usmDHUserKeyTable cell."""

    def test_index_is_both_parts_length_prefixed(self):
        """Engine ID then user name, neither fixed-length nor IMPLIED."""
        instance = keyChangeInstance(
            usmDHUserAuthKeyChange, bytes.fromhex("80001f88"), "ci-sha"
        )
        assert instance == (
            1, 3, 6, 1, 3, 101, 1, 1, 2, 1, 1,
            4, 0x80, 0x00, 0x1F, 0x88,
            6, 99, 105, 45, 115, 104, 97,
        )  # fmt: skip

    def test_user_name_may_be_bytes_or_text(self):
        """Callers hold the name either way; both address the same row."""
        engineId = bytes.fromhex("80001f88")
        assert keyChangeInstance(
            usmDHUserAuthKeyChange, engineId, "user"
        ) == keyChangeInstance(usmDHUserAuthKeyChange, engineId, b"user")

    def test_index_round_trips(self):
        """The engine ID comes back out, which is how a caller learns it.

        A localized key is only usable with the engine ID it is bound to, and a
        row OID the agent handed out is where that engine ID comes from without
        a second discovery exchange.
        """
        engineId = bytes.fromhex("80001f8880809cf06cd99dad6a00000000")
        instance = keyChangeInstance(usmDHUserAuthKeyChange, engineId, b"ci-dh")
        assert parseKeyChangeInstance(usmDHUserAuthKeyChange, instance) == (
            engineId,
            b"ci-dh",
        )

    def test_instance_of_another_column_is_refused(self):
        """Parsing against the wrong column would read the index off by nothing
        and hand back a plausible, wrong engine ID."""
        instance = keyChangeInstance(
            usmDHUserPrivKeyChange, bytes.fromhex("80001f88"), b"user"
        )
        with pytest.raises(ValueError):
            parseKeyChangeInstance(usmDHUserAuthKeyChange, instance)

    @pytest.mark.parametrize(
        "index",
        [
            (),  # no index at all
            (4, 0x80, 0x00),  # engine ID shorter than its length says
            (1, 0x80),  # no user name
            (1, 0x80, 4, 1, 2),  # user name shorter than its length says
            (1, 0x80, 1, 1, 9, 9),  # sub-identifiers left over
        ],
    )
    def test_malformed_index_is_refused(self, index):
        """A row OID that is not two length-prefixed strings names no row."""
        with pytest.raises(ValueError):
            parseKeyChangeInstance(
                usmDHUserAuthKeyChange, usmDHUserAuthKeyChange + index
            )


class TestNoCryptoDependency:
    """The agreement must not drag in a second compiled crypto library.

    Adding one is the standing objection to this feature (#280): the engine
    already carries pycryptodomex, and `cryptography` would be a second. Modular
    exponentiation is `pow` and the one derivation named is PBKDF2, which
    hashlib has, so neither is needed -- and this holds that line.
    """

    def test_module_imports_without_cryptography(self):
        """Importing the primitives loads no cryptographic library at all."""
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                "import sys;"
                "import pysnmp.proto.secmod.rfc2786 as dh;"
                "loaded = [m for m in sys.modules"
                " if m.split('.')[0] in ('cryptography', 'Cryptodome', 'Crypto')];"
                "print(loaded)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "[]"

    def test_agreement_runs_without_cryptography(self):
        """And the agreement itself completes with the standard library only."""
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                "import sys;"
                "sys.modules['cryptography'] = None;"
                "from pysnmp.proto.secmod.rfc2786 import *;"
                "a = generateKeyPair(OAKLEY_GROUP_2);"
                "b = generateKeyPair(OAKLEY_GROUP_2);"
                "print(computeSharedSecret(OAKLEY_GROUP_2, a.private, b.public)"
                " == computeSharedSecret(OAKLEY_GROUP_2, b.private, a.public))",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "True"
