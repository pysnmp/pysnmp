#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Diffie-Hellman USM key management (:RFC:`2786`).

SNMP-USM-DH-OBJECTS-MIB changes a USM key by agreeing a new one over the wire,
so the key itself never crosses it and neither side needs the old one. That is
what makes provisioning a fresh agent remotely practical, where the
:RFC:`3414` ``usmUserAuthKeyChange`` this engine already supports cannot: it
requires knowledge of the key being replaced.

This module is the arithmetic and the encodings. The SNMP exchange that drives
them lives in :mod:`pysnmp.hlapi.asyncio.dh`.

Nothing here needs a cryptographic library. The agreement is modular
exponentiation over parameters the agent publishes, which :func:`pow` does, and
the one key derivation the RFC names is PBKDF2, which :mod:`hashlib` has. The
key lengths involved are the ones USM already defines.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from pyasn1.codec.der import decoder as der_decoder
from pyasn1.codec.der import encoder as der_encoder
from pyasn1.error import PyAsn1Error
from pyasn1.type import namedtype, univ

__all__ = [
    "OAKLEY_GROUP_1",
    "OAKLEY_GROUP_2",
    "DHKeyPair",
    "DHParameters",
    "buildKeyChangeValue",
    "computeSharedSecret",
    "decodeDHParameters",
    "deriveKey",
    "deriveKickstartKeys",
    "encodeDHParameters",
    "generateKeyPair",
    "keyChangeInstance",
    "parseKeyChangeInstance",
    "splitKeyChangeValue",
    "usmDHKickstartMgrPublic",
    "usmDHKickstartMyPublic",
    "usmDHKickstartSecurityName",
    "usmDHParameters",
    "usmDHUserAuthKeyChange",
    "usmDHUserOwnAuthKeyChange",
    "usmDHUserOwnPrivKeyChange",
    "usmDHUserPrivKeyChange",
]


# --- SNMP-USM-DH-OBJECTS-MIB object identifiers ---------------------------
# The MIB lives under `experimental` because IANA assigned it DHKEY-CHANGE 101
# there and never moved it. pysmi bundles the module for anyone who wants the
# symbolic names; these are the numeric forms the exchange needs, so that the
# engine path does not depend on a compiled MIB being present.

#: usmDHParameters, a scalar -- append 0 for the instance.
usmDHParameters = (1, 3, 6, 1, 3, 101, 1, 1, 1)

#: usmDHUserAuthKeyChange, column 1 of usmDHUserKeyTable.
usmDHUserAuthKeyChange = (1, 3, 6, 1, 3, 101, 1, 1, 2, 1, 1)
#: usmDHUserOwnAuthKeyChange, column 2 -- the agent's own key.
usmDHUserOwnAuthKeyChange = (1, 3, 6, 1, 3, 101, 1, 1, 2, 1, 2)
#: usmDHUserPrivKeyChange, column 3.
usmDHUserPrivKeyChange = (1, 3, 6, 1, 3, 101, 1, 1, 2, 1, 3)
#: usmDHUserOwnPrivKeyChange, column 4 -- the agent's own key.
usmDHUserOwnPrivKeyChange = (1, 3, 6, 1, 3, 101, 1, 1, 2, 1, 4)

#: usmDHKickstartMyPublic, column 2 of usmDHKickstartTable.
usmDHKickstartMyPublic = (1, 3, 6, 1, 3, 101, 1, 2, 1, 1, 2)
#: usmDHKickstartMgrPublic, column 3.
usmDHKickstartMgrPublic = (1, 3, 6, 1, 3, 101, 1, 2, 1, 1, 3)
#: usmDHKickstartSecurityName, column 4.
usmDHKickstartSecurityName = (1, 3, 6, 1, 3, 101, 1, 2, 1, 1, 4)


# --- Parameters -----------------------------------------------------------
class _DHParameter(univ.Sequence):
    """PKCS#3 section 9 DHParameter, which is how usmDHParameters is encoded."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("prime", univ.Integer()),
        namedtype.NamedType("base", univ.Integer()),
        namedtype.OptionalNamedType("privateValueLength", univ.Integer()),
    )


@dataclass(frozen=True)
class DHParameters:
    """The prime, base and optional private-value length of an agreement.

    Frozen and made only of integers, so importing this module costs nothing and
    the well-known groups below can be module constants.

    Attributes
    ----------
    prime : int
        The prime modulus `p`.
    base : int
        The generator `g`.
    privateValueLength : int or None
        The optional length `l` in bits that bounds the private exponent. When
        absent the exponent is drawn from the whole interval below `p - 1`.
    """

    prime: int
    base: int
    privateValueLength: int | None = None

    @property
    def primeLength(self) -> int:
        """The prime's length in octets, which is the width of a shared secret."""
        return (self.prime.bit_length() + 7) // 8


#: Oakley Group 1, the 768-bit MODP group of :RFC:`2409#section-6.1`.
OAKLEY_GROUP_1 = DHParameters(
    prime=int(
        "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
        "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
        "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
        "E485B576625E7EC6F44C42E9A63A3620FFFFFFFFFFFFFFFF",
        16,
    ),
    base=2,
)

#: Oakley Group 2, the 1024-bit MODP group of :RFC:`2409#section-6.2`.
#:
#: The MIB encourages one of the two Oakley groups as the default for
#: usmDHParameters, and this is the one Net-SNMP publishes.
OAKLEY_GROUP_2 = DHParameters(
    prime=int(
        "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
        "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
        "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
        "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
        "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381"
        "FFFFFFFFFFFFFFFF",
        16,
    ),
    base=2,
)


def decodeDHParameters(substrate: bytes) -> DHParameters:
    """Decode the DER a usmDHParameters read returns.

    Parameters
    ----------
    substrate : bytes
        The octet string value of usmDHParameters.0.

    Returns
    -------
    DHParameters
        The agreement parameters the agent publishes.

    Raises
    ------
    ValueError
        If the octets are not a PKCS#3 DHParameter, or name a degenerate prime
        or base that no agreement could use.
    """
    try:
        parameter, rest = der_decoder.decode(bytes(substrate), asn1Spec=_DHParameter())
    except PyAsn1Error as exc:
        raise ValueError(f"Malformed usmDHParameters value: {exc}") from exc

    if rest:
        raise ValueError("Trailing octets after the usmDHParameters DHParameter")

    prime = int(parameter["prime"])
    base = int(parameter["base"])

    if prime < 3:
        raise ValueError(f"usmDHParameters names an unusable prime {prime}")
    if not 1 < base < prime:
        raise ValueError(f"usmDHParameters names an unusable base {base}")

    # An absent OPTIONAL component decodes to the schema object rather than to
    # None, and asking a schema object for its value raises.
    privateValueLength = parameter["privateValueLength"]
    if privateValueLength is None or not privateValueLength.isValue:
        length = None
    else:
        length = int(privateValueLength)
        if not 1 < length <= prime.bit_length():
            raise ValueError(
                f"usmDHParameters names an unusable private value length {length}"
            )

    return DHParameters(prime=prime, base=base, privateValueLength=length)


def encodeDHParameters(parameters: DHParameters) -> bytes:
    """Encode parameters as the PKCS#3 DER that usmDHParameters carries."""
    parameter = _DHParameter()
    parameter["prime"] = parameters.prime
    parameter["base"] = parameters.base
    if parameters.privateValueLength is not None:
        parameter["privateValueLength"] = parameters.privateValueLength
    return der_encoder.encode(parameter)


# --- The agreement --------------------------------------------------------
@dataclass(frozen=True)
class DHKeyPair:
    """One side of an agreement: a private exponent and the value to publish.

    Attributes
    ----------
    private : int
        The exponent, which never leaves this process.
    public : bytes
        `g^private mod p`, in the minimal big-endian form the MIB's DHKeyChange
        describes -- `k` octets whose first octet is non-zero.
    """

    private: int
    public: bytes


def _toOctets(value: int, length: int | None = None) -> bytes:
    """Render a non-negative integer big-endian, minimally or to a fixed width."""
    if length is None:
        length = max(1, (value.bit_length() + 7) // 8)
    return value.to_bytes(length, "big")


def generateKeyPair(parameters: DHParameters) -> DHKeyPair:
    """Pick a private exponent and derive the public value to send.

    The exponent comes from :mod:`secrets`, and is drawn from the interval the
    DHKeyChange convention gives: `2^(l-1) <= x < 2^l` when the parameters carry
    a private-value length, and `0 <= x < p-1` otherwise. Exponents below 2 are
    redrawn, since they would publish a public value of 1 or `g`.

    Parameters
    ----------
    parameters : DHParameters
        The agreement parameters, normally read from the agent.

    Returns
    -------
    DHKeyPair
        The private exponent and the public value to put on the wire.
    """
    prime = parameters.prime
    length = parameters.privateValueLength

    while True:
        if length is None:
            private = secrets.randbelow(prime - 1)
        else:
            lower = 1 << (length - 1)
            private = lower + secrets.randbelow(lower)
        if private > 1:
            break

    public = pow(parameters.base, private, prime)
    return DHKeyPair(private=private, public=_toOctets(public))


def computeSharedSecret(
    parameters: DHParameters, private: int, peerPublic: bytes
) -> bytes:
    """Complete the agreement and return the shared secret `sk`.

    The secret is returned at the prime's full width, left-padded with zeros,
    which is what the MIB's "right-most n bits" mapping is counted from.

    Parameters
    ----------
    parameters : DHParameters
        The agreement parameters both sides used.
    private : int
        This side's private exponent.
    peerPublic : bytes
        The other side's public value, as it came off the wire.

    Returns
    -------
    bytes
        `sk`, exactly `parameters.primeLength` octets long.

    Raises
    ------
    ValueError
        If the peer's public value is outside the multiplicative group, which
        no honest peer sends and which would leak the exponent.
    """
    peer = int.from_bytes(bytes(peerPublic), "big")

    if not 1 < peer < parameters.prime - 1:
        raise ValueError("Peer Diffie-Hellman public value is out of range")

    return _toOctets(pow(peer, private, parameters.prime), parameters.primeLength)


def deriveKey(sharedSecret: bytes, keyLength: int) -> bytes:
    """Take the operational key out of a shared secret.

    Every DHKeyChange object in the MIB maps `sk` to its key the same way: the
    right-most n bits, where n is what the row's auth or privacy protocol needs.
    The result is a localized key -- it is already bound to the agent whose
    parameters produced it, so it is used as-is rather than run through
    :RFC:`3414` key localization.

    Parameters
    ----------
    sharedSecret : bytes
        The secret from :func:`computeSharedSecret`.
    keyLength : int
        The key length in octets the protocol needs.

    Returns
    -------
    bytes
        The right-most `keyLength` octets of the secret.

    Raises
    ------
    ValueError
        If the secret is shorter than the key asked for.
    """
    if keyLength <= 0:
        raise ValueError(f"Key length {keyLength} is not a length")
    if len(sharedSecret) < keyLength:
        raise ValueError(
            f"Shared secret of {len(sharedSecret)} octets cannot yield a "
            f"{keyLength}-octet key"
        )
    return bytes(sharedSecret[-keyLength:])


# The salts and the iteration count usmDHKickstartMgrPublic names. The RFC
# points out that the salts are just the first two words of the BLOWFISH key
# schedule and could have been any random bits; they are fixed by the MIB.
_KICKSTART_AUTH_SALT = bytes.fromhex("98dfb5ac")
_KICKSTART_PRIV_SALT = bytes.fromhex("d1310ba6")
_KICKSTART_ITERATIONS = 500


def deriveKickstartKeys(
    sharedSecret: bytes, authKeyLength: int = 16, privKeyLength: int = 16
) -> tuple[bytes, bytes]:
    """Derive the pair of keys a kickstart row bootstraps a user with.

    Unlike a key change, kickstart does not take the right-most bits of `sk`: it
    runs PBKDF2 over the whole secret, once per key, with the two salts the MIB
    fixes and a PRF of HMAC-SHA-1.

    The defaults are the lengths the MIB's own table names, where the row it
    creates is usmHMACMD5AuthProtocol with usmDESPrivProtocol.

    Parameters
    ----------
    sharedSecret : bytes
        The secret from :func:`computeSharedSecret`.
    authKeyLength : int, optional
        Octets of authentication key to derive.
    privKeyLength : int, optional
        Octets of privacy key to derive.

    Returns
    -------
    tuple of bytes
        The authentication key and the privacy key, in that order.
    """
    authKey = hashlib.pbkdf2_hmac(
        "sha1",
        bytes(sharedSecret),
        _KICKSTART_AUTH_SALT,
        _KICKSTART_ITERATIONS,
        authKeyLength,
    )
    privKey = hashlib.pbkdf2_hmac(
        "sha1",
        bytes(sharedSecret),
        _KICKSTART_PRIV_SALT,
        _KICKSTART_ITERATIONS,
        privKeyLength,
    )
    return authKey, privKey


# --- The DHKeyChange value ------------------------------------------------
def buildKeyChangeValue(peerPublic: bytes, ownPublic: bytes) -> bytes:
    """Build the octet string a DHKeyChange object is SET to.

    A successful SET carries the value just read from the object followed by the
    value being offered in return. The agent compares the first half against
    what it published -- a mismatch is `wrongValue` -- and takes the second half
    as the manager's public value.

    Both halves must be the same width, because the agent splits the value down
    the middle rather than parsing it. An own public value that is short (its
    top octet came out zero) is left-padded to match; one that is longer than
    the agent's cannot be sent at all, and the caller should draw another key
    pair.

    Parameters
    ----------
    peerPublic : bytes
        The value just read from the object.
    ownPublic : bytes
        This side's public value.

    Returns
    -------
    bytes
        The concatenation to SET.

    Raises
    ------
    ValueError
        If the own public value will not fit in the peer's width.
    """
    peerPublic = bytes(peerPublic)
    ownPublic = bytes(ownPublic)

    if not peerPublic:
        raise ValueError("The agent published an empty Diffie-Hellman public value")
    if len(ownPublic) > len(peerPublic):
        raise ValueError(
            f"A {len(ownPublic)}-octet public value does not fit the agent's "
            f"{len(peerPublic)}-octet half of the DHKeyChange value"
        )

    return peerPublic + ownPublic.rjust(len(peerPublic), b"\x00")


def splitKeyChangeValue(value: bytes) -> tuple[bytes, bytes]:
    """Split a DHKeyChange value into the two public values it carries.

    Raises
    ------
    ValueError
        If the value is empty or of odd length, neither of which can be two
        halves.
    """
    value = bytes(value)

    if not value or len(value) % 2:
        raise ValueError(
            f"A DHKeyChange value of {len(value)} octets is not two public values"
        )

    half = len(value) // 2
    return value[:half], value[half:]


def keyChangeInstance(
    column: tuple[int, ...], securityEngineId: bytes, userName: bytes | str
) -> tuple[int, ...]:
    """Build the instance OID of a usmDHUserKeyTable cell.

    The table is indexed as usmUserTable is, by engine ID and user name, and
    neither index is fixed-length or IMPLIED, so both go on the wire
    length-prefixed.

    Parameters
    ----------
    column : tuple of int
        One of the four key-change column OIDs in this module.
    securityEngineId : bytes
        The authoritative engine ID of the agent holding the row.
    userName : bytes or str
        The USM user name the row belongs to.

    Returns
    -------
    tuple of int
        The full instance OID to GET or SET.
    """
    if isinstance(userName, str):
        userName = userName.encode("utf-8")

    securityEngineId = bytes(securityEngineId)
    userName = bytes(userName)

    return (
        tuple(column)
        + (len(securityEngineId),)
        + tuple(securityEngineId)
        + (len(userName),)
        + tuple(userName)
    )


def parseKeyChangeInstance(
    column: tuple[int, ...], instance: tuple[int, ...]
) -> tuple[bytes, bytes]:
    """Take a usmDHUserKeyTable instance OID apart again.

    The inverse of :func:`keyChangeInstance`. Worth having because the engine ID
    is otherwise only observable through a v3 discovery exchange, and a row OID
    the agent handed out already carries it.

    Parameters
    ----------
    column : tuple of int
        The column OID the instance belongs to.
    instance : tuple of int
        The full instance OID.

    Returns
    -------
    tuple of bytes
        The engine ID and the user name.

    Raises
    ------
    ValueError
        If the OID is not an instance of that column, or its index is not the
        two length-prefixed strings the table is indexed by.
    """
    column = tuple(column)
    instance = tuple(instance)

    if instance[: len(column)] != column:
        raise ValueError("That OID is not an instance of that column")

    index = instance[len(column) :]

    if not index:
        raise ValueError("A usmDHUserKeyTable instance OID carries an index")

    engineIdLength = index[0]
    engineId = index[1 : 1 + engineIdLength]
    rest = index[1 + engineIdLength :]

    if len(engineId) != engineIdLength or not rest:
        raise ValueError("Truncated engine ID in a usmDHUserKeyTable index")

    userNameLength = rest[0]
    userName = rest[1 : 1 + userNameLength]

    if len(userName) != userNameLength or len(rest) != 1 + userNameLength:
        raise ValueError("Malformed user name in a usmDHUserKeyTable index")

    return bytes(engineId), bytes(userName)
