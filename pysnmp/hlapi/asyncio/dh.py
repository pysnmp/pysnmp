#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Diffie-Hellman USM key change over the wire (:RFC:`2786`).

The arithmetic is in :mod:`pysnmp.proto.secmod.rfc2786`; what is here is the
exchange that carries it: read the agent's parameters, read the public value it
published for the row, offer one back, and derive the key both sides now hold.

The key that comes back is already localized to the agent, because it is
derived from a secret only that agent could have computed. It goes straight
into :py:class:`~pysnmp.hlapi.UsmUserData` as
:py:class:`~pysnmp.hlapi.usmKeyTypeLocalized`, with no :RFC:`3414` key
localization step.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from pysnmp._aliases import install as _installAliases
from pysnmp.error import PySnmpError
from pysnmp.hlapi.asyncio.cmdgen import get_cmd, next_cmd, set_cmd
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.proto.rfc1905 import EndOfMibView, NoSuchInstance, NoSuchObject
from pysnmp.proto.secmod.eso.priv import aes192, aes256, des3
from pysnmp.proto.secmod.rfc2786 import (
    DHParameters,
    buildKeyChangeValue,
    computeSharedSecret,
    decodeDHParameters,
    deriveKey,
    generateKeyPair,
    keyChangeInstance,
    parseKeyChangeInstance,
    usmDHParameters,
    usmDHUserAuthKeyChange,
    usmDHUserOwnAuthKeyChange,
    usmDHUserOwnPrivKeyChange,
    usmDHUserPrivKeyChange,
)
from pysnmp.proto.secmod.rfc3414.auth import hmacmd5, hmacsha
from pysnmp.proto.secmod.rfc3414.priv import des
from pysnmp.proto.secmod.rfc3826.priv import aes
from pysnmp.proto.secmod.rfc7860.auth import hmacsha2
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

__all__ = [
    "DHKeyChangeError",
    "DHKeyChangeResult",
    "dh_key_change",
]


class DHKeyChangeError(PySnmpError):
    """A Diffie-Hellman key change did not complete.

    Raised rather than returned, because a key change that half happened leaves
    the caller unable to talk to the agent, and a return value is too easy to
    ignore.

    Attributes
    ----------
    candidate : DHKeyChangeResult or None
        Set when the SET was the step that failed, and then the failure is
        ambiguous: the agent may have applied the change and lost the response.
        :RFC:`2786` defines no recovery for that, so the way to find out is to
        try this key. None for every other step, where nothing was changed.
    """

    def __init__(self, message: str, candidate: DHKeyChangeResult | None = None):
        """Record the message and, for a failed SET, the key that may be live."""
        super().__init__(message)
        self.candidate = candidate


class DHKeyChangeResult(NamedTuple):
    """What a completed key change produced.

    Attributes
    ----------
    key : bytes
        The new key, already localized to this agent.
    securityEngineId : bytes
        The agent's authoritative engine ID. Returned because a localized key is
        only usable with the engine ID it is bound to, and this exchange has
        already learned it -- pass both to
        :py:class:`~pysnmp.hlapi.UsmUserData`.
    instance : tuple of int
        The DHKeyChange instance that was SET.
    parameters : pysnmp.proto.secmod.rfc2786.DHParameters
        The agreement parameters the agent published.
    """

    key: bytes
    securityEngineId: bytes
    instance: tuple[int, ...]
    parameters: DHParameters


# The localized key length each protocol takes, which is how many right-most
# bits of the shared secret become the key. Sourced from the security services
# themselves wherever they state it, so this cannot drift from what the engine
# will do with the result.
_AUTH_KEY_LENGTHS: dict[tuple[int, ...], int] = {
    # RFC 3414 localizes to one digest: 16 octets for MD5, 20 for SHA-1.
    hmacmd5.HmacMd5.serviceID: 16,
    hmacsha.HmacSha.serviceID: 20,
    # Widened from the fixed-length OID tuples the service states them with.
    **{tuple(oid): length for oid, length in hmacsha2.HmacSha2.keyLengths.items()},
}

_PRIV_KEY_LENGTHS: dict[tuple[int, ...], int] = {
    service.serviceID: service.keySize
    for service in (
        des.Des,
        des3.Des3,
        aes.Aes,
        aes192.Aes192,
        aes192.AesBlumenthal192,
        aes256.Aes256,
        aes256.AesBlumenthal256,
    )
}

_MISSING_VALUES = (NoSuchObject, NoSuchInstance, EndOfMibView)

# A public value whose leading octet came out zero encodes short, and the agent
# splits a DHKeyChange value down the middle rather than parsing it, so a short
# one has to be redrawn. It happens about once in 256 draws; eight attempts put
# the chance of giving up below one in a trillion.
_PUBLIC_VALUE_ATTEMPTS = 8

# Enough of usmDHUserKeyTable to find one row. The table has a row per USM user,
# and an agent with more users than this is not one being provisioned by hand.
_ROW_SCAN_LIMIT = 256


def _failed(errorIndication: Any, errorStatus: Any, what: str) -> None:
    """Turn either flavour of SNMP failure into one exception."""
    if errorIndication:
        raise DHKeyChangeError(f"{what}: {errorIndication}")
    if errorStatus:
        raise DHKeyChangeError(f"{what}: {errorStatus.prettyPrint()}")


def _octets(value: Any, what: str) -> bytes:
    """Take the octets out of a var-bind value, refusing the absent ones."""
    if isinstance(value, _MISSING_VALUES):
        raise DHKeyChangeError(
            f"{what} is not available on this agent "
            f"(it may not implement SNMP-USM-DH-OBJECTS-MIB)"
        )
    if not isinstance(value, OctetString):
        raise DHKeyChangeError(f"{what} is {type(value).__name__}, not an OCTET STRING")
    return value.asOctets()


def _column(keyType: str, own: bool) -> tuple[int, ...]:
    """Pick the DHKeyChange column a request names."""
    if keyType == "auth":
        return usmDHUserOwnAuthKeyChange if own else usmDHUserAuthKeyChange
    if keyType == "priv":
        return usmDHUserOwnPrivKeyChange if own else usmDHUserPrivKeyChange
    raise ValueError(f"keyType must be 'auth' or 'priv', not {keyType!r}")


def _keyLength(keyType: str, authData: Any, keyLength: int | None) -> int:
    """Work out how many octets of key the row's protocol takes."""
    if keyLength is not None:
        return keyLength

    if keyType == "auth":
        protocol = tuple(getattr(authData, "authProtocol", ()) or ())
        lengths = _AUTH_KEY_LENGTHS
    else:
        protocol = tuple(getattr(authData, "privProtocol", ()) or ())
        lengths = _PRIV_KEY_LENGTHS

    try:
        return lengths[protocol]
    except KeyError:
        raise DHKeyChangeError(
            f"No key length known for {keyType} protocol {protocol}; "
            f"pass keyLength to say how many octets the agent expects"
        ) from None


async def _readParameters(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    **options: Any,
) -> DHParameters:
    """Read and decode usmDHParameters.0."""
    errorIndication, errorStatus, _errorIndex, varBinds = await get_cmd(
        snmpEngine,
        authData,
        transportTarget,
        contextData,
        ObjectType(ObjectIdentity(usmDHParameters + (0,))),
        **options,
    )
    _failed(errorIndication, errorStatus, "Reading usmDHParameters")

    substrate = _octets(varBinds[0][1], "usmDHParameters")
    try:
        return decodeDHParameters(substrate)
    except ValueError as exc:
        raise DHKeyChangeError(f"Reading usmDHParameters: {exc}") from exc


async def _findRow(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    column: tuple[int, ...],
    userName: bytes,
    **options: Any,
) -> tuple[tuple[int, ...], bytes]:
    """Walk a DHKeyChange column for the row belonging to `userName`.

    Saves the caller from having to know the agent's engine ID, which is the
    first half of the row index and is otherwise only observable through a v3
    discovery exchange. The walk returns the row's current public value too, so
    finding the row costs nothing extra.
    """
    # The index is engine ID then user name, each length-prefixed, so a row for
    # this user ends with these sub-identifiers.
    suffix = (len(userName),) + tuple(userName)
    varBind = ObjectType(ObjectIdentity(column))

    for _ in range(_ROW_SCAN_LIMIT):
        errorIndication, errorStatus, _errorIndex, table = await next_cmd(
            snmpEngine,
            authData,
            transportTarget,
            contextData,
            varBind,
            **options,
        )
        _failed(errorIndication, errorStatus, "Walking usmDHUserKeyTable")

        if not table or not table[0]:
            break

        name, value = table[0][0]
        instance = tuple(name)

        if instance[: len(column)] != tuple(column):
            break
        if isinstance(value, EndOfMibView):
            break

        if instance[-len(suffix) :] == suffix:
            return instance, _octets(value, "usmDHUserKeyTable cell")

        varBind = ObjectType(ObjectIdentity(instance))

    raise DHKeyChangeError(
        f"No usmDHUserKeyTable row for user {userName.decode('utf-8', 'replace')!r}; "
        f"pass securityEngineId if the agent does not allow walking the table"
    )


async def _readCell(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    instance: tuple[int, ...],
    **options: Any,
) -> bytes:
    """Read one DHKeyChange cell, for when the caller named the engine ID."""
    errorIndication, errorStatus, _errorIndex, varBinds = await get_cmd(
        snmpEngine,
        authData,
        transportTarget,
        contextData,
        ObjectType(ObjectIdentity(instance)),
        **options,
    )
    _failed(errorIndication, errorStatus, "Reading usmDHUserKeyTable")
    return _octets(varBinds[0][1], "usmDHUserKeyTable cell")


async def dh_key_change(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    keyType: str = "auth",
    *,
    own: bool = False,
    userName: bytes | str | None = None,
    securityEngineId: bytes | None = None,
    keyLength: int | None = None,
    **options: Any,
) -> DHKeyChangeResult:
    r"""Change a USM key by Diffie-Hellman agreement (:RFC:`2786`).

    Neither the old key nor the new one crosses the wire, and the old one is not
    needed to run this -- only write access to the row. That is what
    ``usmUserAuthKeyChange`` cannot offer, and what makes provisioning an agent
    remotely practical.

    The agent installs the new key when the SET commits, so the credentials used
    for this call stop working the moment it returns. Build fresh
    :py:class:`~pysnmp.hlapi.UsmUserData` from the returned key, passing
    ``authKeyType=usmKeyTypeLocalized``.

    Parameters
    ----------
    snmpEngine : SnmpEngine
        Class instance representing SNMP engine.
    authData : UsmUserData
        The credentials to run the exchange under. Their user name names the row
        unless `userName` overrides it, and their protocols say how long the new
        key is unless `keyLength` overrides it.
    transportTarget : TransportTarget
        Class instance representing transport type along with SNMP peer address.
    contextData : ContextData
        Class instance representing SNMP ContextEngineId and ContextName values.
    keyType : str, optional
        ``"auth"`` for the authentication key, ``"priv"`` for the privacy key.
    own : bool, optional
        Use the ``usmDHUserOwn*`` column, which is how an agent changes its own
        key rather than the named user's.
    userName : bytes or str, optional
        The USM user whose row to change, when it is not the one authenticating.
    securityEngineId : bytes, optional
        The agent's authoritative engine ID. Given, the row is addressed
        directly; omitted, the table is walked to find it.
    keyLength : int, optional
        Octets of key to derive, when the protocol in `authData` is not the one
        the row uses.
    \*\*options :
        Passed through to the underlying commands.

    Returns
    -------
    DHKeyChangeResult
        The new localized key, the instance that was set and the parameters used.

    Raises
    ------
    DHKeyChangeError
        If any step fails. Everything is derived before the SET, so the agent's
        key is unchanged unless the SET itself was the step that failed -- and
        that case carries a `candidate` result, because a failed SET may still
        have been applied. A transport target with retries turns a lost response
        into a `wrongValue` on the retransmission rather than a timeout; pass a
        target with ``retries=0`` if a timeout is the clearer signal for your
        recovery path.

    Examples
    --------
    >>> import asyncio
    >>> from pysnmp.hlapi.asyncio import *
    >>> from pysnmp.proto.rfc1902 import OctetString
    >>>
    >>> async def run():
    ...     result = await dh_key_change(
    ...         SnmpEngine(),
    ...         UsmUserData('user', 'authkey1'),
    ...         await UdpTransportTarget.create(('localhost', 161)),
    ...         ContextData(),
    ...     )
    ...     return UsmUserData(
    ...         'user',
    ...         result.key,
    ...         authKeyType=usmKeyTypeLocalized,
    ...         securityEngineId=OctetString(result.securityEngineId),
    ...     )
    >>>
    >>> rekeyed = asyncio.run(run())  # doctest: +SKIP
    """
    column = _column(keyType, own)
    wanted = _keyLength(keyType, authData, keyLength)

    if userName is None:
        userName = getattr(authData, "userName", None)
        if userName is None:
            raise DHKeyChangeError("No user name to change a key for")
    if isinstance(userName, str):
        userName = userName.encode("utf-8")

    parameters = await _readParameters(
        snmpEngine, authData, transportTarget, contextData, **options
    )

    if securityEngineId is None:
        instance, agentPublic = await _findRow(
            snmpEngine,
            authData,
            transportTarget,
            contextData,
            column,
            userName,
            **options,
        )
    else:
        instance = keyChangeInstance(column, securityEngineId, userName)
        agentPublic = await _readCell(
            snmpEngine, authData, transportTarget, contextData, instance, **options
        )

    for _ in range(_PUBLIC_VALUE_ATTEMPTS):
        keyPair = generateKeyPair(parameters)
        if len(keyPair.public) <= len(agentPublic):
            break
    else:
        raise DHKeyChangeError(
            "Could not draw a public value that fits the agent's half of the "
            "DHKeyChange value"
        )

    # Everything the result needs is computable before the SET, and the SET is
    # the one step that cannot be undone. Deriving first means a peer public
    # value out of range, a key length that cannot be met, or an index that does
    # not parse costs nothing; deriving afterwards would leave the agent re-keyed
    # with the caller holding no key for it.
    try:
        secret = computeSharedSecret(parameters, keyPair.private, agentPublic)
        candidate = DHKeyChangeResult(
            key=deriveKey(secret, wanted),
            securityEngineId=parseKeyChangeInstance(column, instance)[0],
            instance=instance,
            parameters=parameters,
        )
    except ValueError as exc:
        raise DHKeyChangeError(
            f"Refusing the key change, because its result could not be derived "
            f"and the agent would have been left re-keyed to an unknown value: "
            f"{exc}"
        ) from exc

    errorIndication, errorStatus, _errorIndex, _varBinds = await set_cmd(
        snmpEngine,
        authData,
        transportTarget,
        contextData,
        ObjectType(
            ObjectIdentity(instance),
            OctetString(buildKeyChangeValue(agentPublic, keyPair.public)),
        ),
        **options,
    )

    if errorIndication or errorStatus:
        # A failed SET does not mean the key is unchanged. No response at all may
        # be a lost reply to a SET that committed, and a `wrongValue` may be the
        # agent refusing a retransmission of a SET it has already applied -- it
        # publishes a fresh public value on success, so the second copy no longer
        # matches. Hand back the candidate rather than leaving the caller to
        # assume the old key still works.
        detail = errorIndication or errorStatus.prettyPrint()
        raise DHKeyChangeError(
            f"Setting the DHKeyChange object: {detail}. The agent may still have "
            f"applied it, so try authenticating with the candidate key on this "
            f"error before assuming the old key is live",
            candidate=candidate,
        )

    return candidate


#: The camelCase spelling this name used to have. Served by ``__getattr__``
#: below rather than bound here, so that using it warns -- see
#: :py:mod:`pysnmp._aliases`.
_DEPRECATED_ALIASES = {"dhKeyChange": "dh_key_change"}

__getattr__, __dir__ = _installAliases(__name__, globals(), _DEPRECATED_ALIASES)
