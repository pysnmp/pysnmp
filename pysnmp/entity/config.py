#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

import warnings
from typing import Any

from pysnmp import debug, error
from pysnmp.carrier.asyncio.dgram import udp, udp6, unix
from pysnmp.proto import rfc1902, rfc1905
from pysnmp.proto.secmod import cipherbackend
from pysnmp.proto.secmod.eso.priv import aes192, aes256, des3
from pysnmp.proto.secmod.rfc3414.auth import hmacmd5, hmacsha, noauth
from pysnmp.proto.secmod.rfc3414.priv import des, nopriv
from pysnmp.proto.secmod.rfc3826.priv import aes
from pysnmp.proto.secmod.rfc7860.auth import hmacsha2

# A shortcut to popular constants

# Transports
snmpUDPDomain = udp.snmpUDPDomain
snmpUDP6Domain = udp6.snmpUDP6Domain
snmpLocalDomain = unix.snmpLocalDomain

# Auth protocol
usmHMACMD5AuthProtocol = hmacmd5.HmacMd5.serviceID
usmHMACSHAAuthProtocol = hmacsha.HmacSha.serviceID
usmHMAC128SHA224AuthProtocol = hmacsha2.HmacSha2.sha224ServiceID
usmHMAC192SHA256AuthProtocol = hmacsha2.HmacSha2.sha256ServiceID
usmHMAC256SHA384AuthProtocol = hmacsha2.HmacSha2.sha384ServiceID
usmHMAC384SHA512AuthProtocol = hmacsha2.HmacSha2.sha512ServiceID

usmNoAuthProtocol = noauth.NoAuth.serviceID
"""No authentication service"""

# Privacy protocol
usmDESPrivProtocol = des.Des.serviceID
usm3DESEDEPrivProtocol = des3.Des3.serviceID
usmAesCfb128Protocol = aes.Aes.serviceID
usmAesBlumenthalCfb192Protocol = (
    aes192.AesBlumenthal192.serviceID
)  # semi-standard but not widely used
usmAesBlumenthalCfb256Protocol = (
    aes256.AesBlumenthal256.serviceID
)  # semi-standard but not widely used
usmAesCfb192Protocol = aes192.Aes192.serviceID  # non-standard but used by many vendors
usmAesCfb256Protocol = aes256.Aes256.serviceID  # non-standard but used by many vendors
usmNoPrivProtocol = nopriv.NoPriv.serviceID

# USM key types (PYSNMP-USM-MIB::pysnmpUsmKeyType)
usmKeyTypePassphrase = 0
usmKeyTypeMaster = 1
usmKeyTypeLocalized = 2

# Protocols that are still implemented for interoperability with deployed
# equipment, but that must not be chosen for new deployments. Configuring one
# of these emits a `PySnmpWeakCryptoWarning`.
WEAK_PROTOCOLS: dict[Any, str] = {
    usmDESPrivProtocol: (
        "usmDESPrivProtocol (DES-CBC) has a 56-bit effective key and is "
        "disallowed for encryption by NIST SP 800-131A. Use "
        "usmAesCfb128Protocol instead."
    ),
    usm3DESEDEPrivProtocol: (
        "usm3DESEDEPrivProtocol (3DES-EDE) has a 64-bit block and is "
        "vulnerable to Sweet32 (CVE-2016-2183); NIST SP 800-131A Rev 2 "
        "disallows it for encryption. Use usmAesCfb128Protocol instead."
    ),
    usmHMACMD5AuthProtocol: (
        "usmHMACMD5AuthProtocol relies on MD5, deprecated by RFC 6151. Use "
        "usmHMAC192SHA256AuthProtocol instead."
    ),
}

# Protocols that are cryptographically sound but were never standardised by
# the IETF. They are needed to talk to some vendors' equipment, and are not a
# portable choice. Configuring one emits a `PySnmpNonStandardCryptoWarning`.
NON_STANDARD_PROTOCOLS: dict[Any, str] = {
    usmAesBlumenthalCfb192Protocol: "usmAesBlumenthalCfb192Protocol",
    usmAesBlumenthalCfb256Protocol: "usmAesBlumenthalCfb256Protocol",
    usmAesCfb192Protocol: "usmAesCfb192Protocol",
    usmAesCfb256Protocol: "usmAesCfb256Protocol",
}


def __warnAboutProtocol(protocol: Any, stacklevel: int) -> None:
    reason = WEAK_PROTOCOLS.get(protocol)
    if reason is not None:
        warnings.warn(reason, error.PySnmpWeakCryptoWarning, stacklevel=stacklevel)
        return

    name = NON_STANDARD_PROTOCOLS.get(protocol)
    if name is not None:
        warnings.warn(
            f"{name} is based on an expired IETF draft rather than a published "
            f"standard, and interoperates only with equipment implementing the "
            f"same draft. usmAesCfb128Protocol (RFC 3826) is the standards-track "
            f"privacy protocol.",
            error.PySnmpNonStandardCryptoWarning,
            stacklevel=stacklevel,
        )


def __checkPrivBackend(privProtocol: Any) -> None:
    if privProtocol not in privServices:
        raise error.PySnmpError(f"Unknown privacy protocol {privProtocol}")

    if privProtocol == usmNoPrivProtocol:
        return

    if not cipherbackend.isAvailable():
        raise error.PySnmpError(cipherbackend.INSTALL_HINT)


# Auth services
authServices: dict[Any, Any] = {
    hmacmd5.HmacMd5.serviceID: hmacmd5.HmacMd5(),
    hmacsha.HmacSha.serviceID: hmacsha.HmacSha(),
    hmacsha2.HmacSha2.sha224ServiceID: hmacsha2.HmacSha2(hmacsha2.HmacSha2.sha224ServiceID),
    hmacsha2.HmacSha2.sha256ServiceID: hmacsha2.HmacSha2(hmacsha2.HmacSha2.sha256ServiceID),
    hmacsha2.HmacSha2.sha384ServiceID: hmacsha2.HmacSha2(hmacsha2.HmacSha2.sha384ServiceID),
    hmacsha2.HmacSha2.sha512ServiceID: hmacsha2.HmacSha2(hmacsha2.HmacSha2.sha512ServiceID),
    noauth.NoAuth.serviceID: noauth.NoAuth(),
}

# Privacy services
privServices: dict[Any, Any] = {
    des.Des.serviceID: des.Des(),
    des3.Des3.serviceID: des3.Des3(),
    aes.Aes.serviceID: aes.Aes(),
    aes192.AesBlumenthal192.serviceID: aes192.AesBlumenthal192(),
    aes256.AesBlumenthal256.serviceID: aes256.AesBlumenthal256(),
    aes192.Aes192.serviceID: aes192.Aes192(),  # non-standard
    aes256.Aes256.serviceID: aes256.Aes256(),  # non-standard
    nopriv.NoPriv.serviceID: nopriv.NoPriv(),
}


def __cookV1SystemInfo(snmpEngine: Any, communityIndex: str) -> tuple[Any, Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (snmpEngineID,) = mibBuilder.importSymbols("__SNMP-FRAMEWORK-MIB", "snmpEngineID")
    (snmpCommunityEntry,) = mibBuilder.importSymbols("SNMP-COMMUNITY-MIB", "snmpCommunityEntry")
    tblIdx = snmpCommunityEntry.getInstIdFromIndices(communityIndex)
    return snmpCommunityEntry, tblIdx, snmpEngineID


def addV1System(
    snmpEngine: Any,
    communityIndex: str,
    communityName: Any,
    contextEngineId: Any | None = None,
    contextName: Any | None = None,
    transportTag: Any | None = None,
    securityName: Any | None = None,
) -> None:
    (snmpCommunityEntry, tblIdx, snmpEngineID) = __cookV1SystemInfo(snmpEngine, communityIndex)

    if contextEngineId is None:
        contextEngineId = snmpEngineID.syntax
    else:
        contextEngineId = snmpEngineID.syntax.clone(contextEngineId)

    if contextName is None:
        contextName = b""

    securityName = securityName if securityName is not None else communityIndex

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpCommunityEntry.name + (8,) + tblIdx, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (snmpCommunityEntry.name + (1,) + tblIdx, communityIndex),
            (snmpCommunityEntry.name + (2,) + tblIdx, communityName),
            (snmpCommunityEntry.name + (3,) + tblIdx, securityName),
            (snmpCommunityEntry.name + (4,) + tblIdx, contextEngineId),
            (snmpCommunityEntry.name + (5,) + tblIdx, contextName),
            (snmpCommunityEntry.name + (6,) + tblIdx, transportTag),
            (snmpCommunityEntry.name + (7,) + tblIdx, "nonVolatile"),
            (snmpCommunityEntry.name + (8,) + tblIdx, "createAndGo"),
        )
    )

    debug.logger & debug.flagSM and debug.logger(
        "addV1System: added new table entry "
        'communityIndex "%s" communityName "%s" securityName "%s" '
        'contextEngineId "%s" contextName "%s" transportTag '
        '"%s"'
        % (
            communityIndex,
            debug.prettify(communityName),
            debug.prettify(securityName),
            debug.prettify(contextEngineId),
            debug.prettify(contextName),
            debug.prettify(transportTag),
        )
    )


def delV1System(snmpEngine: Any, communityIndex: str) -> None:
    (snmpCommunityEntry, tblIdx, snmpEngineID) = __cookV1SystemInfo(snmpEngine, communityIndex)
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpCommunityEntry.name + (8,) + tblIdx, "destroy"),)
    )

    debug.logger & debug.flagSM and debug.logger(
        'delV1System: deleted table entry by communityIndex "%s"' % (communityIndex,)
    )


def __cookV3UserInfo(
    snmpEngine: Any, securityName: Any, securityEngineId: Any | None
) -> tuple[Any, Any, Any, Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (snmpEngineID,) = mibBuilder.importSymbols("__SNMP-FRAMEWORK-MIB", "snmpEngineID")

    if securityEngineId is None:
        securityEngineId = snmpEngineID.syntax
    else:
        securityEngineId = snmpEngineID.syntax.clone(securityEngineId)

    (usmUserEntry,) = mibBuilder.importSymbols("SNMP-USER-BASED-SM-MIB", "usmUserEntry")
    tblIdx1 = usmUserEntry.getInstIdFromIndices(securityEngineId, securityName)

    (pysnmpUsmSecretEntry,) = mibBuilder.importSymbols("PYSNMP-USM-MIB", "pysnmpUsmSecretEntry")
    tblIdx2 = pysnmpUsmSecretEntry.getInstIdFromIndices(securityName)

    return securityEngineId, usmUserEntry, tblIdx1, pysnmpUsmSecretEntry, tblIdx2


def addV3User(
    snmpEngine: Any,
    userName: Any,
    authProtocol: Any = usmNoAuthProtocol,
    authKey: Any | None = None,
    privProtocol: Any = usmNoPrivProtocol,
    privKey: Any | None = None,
    securityEngineId: Any | None = None,
    securityName: Any | None = None,
    authKeyType: int = usmKeyTypePassphrase,
    privKeyType: int = usmKeyTypePassphrase,
    # deprecated parameter
    contextEngineId: Any | None = None,
) -> None:

    __checkPrivBackend(privProtocol)
    __warnAboutProtocol(authProtocol, stacklevel=3)
    __warnAboutProtocol(privProtocol, stacklevel=3)

    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    if securityName is None:
        securityName = userName

    if securityEngineId is None:  # backward compatibility
        securityEngineId = contextEngineId

    (securityEngineId, usmUserEntry, tblIdx1, pysnmpUsmSecretEntry, tblIdx2) = __cookV3UserInfo(
        snmpEngine, securityName, securityEngineId
    )

    # Load augmenting table before creating new row in base one
    (pysnmpUsmKeyEntry,) = mibBuilder.importSymbols("PYSNMP-USM-MIB", "pysnmpUsmKeyEntry")

    # Load clone-from (may not be needed)
    (zeroDotZero,) = mibBuilder.importSymbols("SNMPv2-SMI", "zeroDotZero")

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((usmUserEntry.name + (13,) + tblIdx1, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (usmUserEntry.name + (2,) + tblIdx1, userName),
            (usmUserEntry.name + (3,) + tblIdx1, securityName),
            (usmUserEntry.name + (4,) + tblIdx1, zeroDotZero.name),
            (usmUserEntry.name + (5,) + tblIdx1, authProtocol),
            (usmUserEntry.name + (8,) + tblIdx1, privProtocol),
            (usmUserEntry.name + (13,) + tblIdx1, "createAndGo"),
        )
    )

    if authProtocol not in authServices:
        raise error.PySnmpError(f"Unknown auth protocol {authProtocol}")

    (pysnmpUsmKeyType,) = mibBuilder.importSymbols("__PYSNMP-USM-MIB", "pysnmpUsmKeyType")

    authKeyType = pysnmpUsmKeyType.syntax.clone(authKeyType)

    # Localize authentication key unless given

    authKey = authKey and rfc1902.OctetString(authKey)

    masterAuthKey = localAuthKey = authKey

    if authKeyType < usmKeyTypeMaster:  # pass phrase is given
        masterAuthKey = authServices[authProtocol].hashPassphrase(authKey or b"")

    if authKeyType < usmKeyTypeLocalized:  # pass phrase or master key is given
        localAuthKey = authServices[authProtocol].localizeKey(masterAuthKey, securityEngineId)

    # Localize privacy key unless given

    privKeyType = pysnmpUsmKeyType.syntax.clone(privKeyType)

    privKey = privKey and rfc1902.OctetString(privKey)

    masterPrivKey = localPrivKey = privKey

    if privKeyType < usmKeyTypeMaster:  # pass phrase is given
        masterPrivKey = privServices[privProtocol].hashPassphrase(authProtocol, privKey or b"")

    if privKeyType < usmKeyTypeLocalized:  # pass phrase or master key is given
        localPrivKey = privServices[privProtocol].localizeKey(
            authProtocol, masterPrivKey, securityEngineId
        )

    # Commit only the keys we have

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((pysnmpUsmKeyEntry.name + (1,) + tblIdx1, localAuthKey),)
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((pysnmpUsmKeyEntry.name + (2,) + tblIdx1, localPrivKey),)
    )

    if authKeyType < usmKeyTypeLocalized:
        snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
            ((pysnmpUsmKeyEntry.name + (3,) + tblIdx1, masterAuthKey),)
        )

    if privKeyType < usmKeyTypeLocalized:
        snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
            ((pysnmpUsmKeyEntry.name + (4,) + tblIdx1, masterPrivKey),)
        )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((pysnmpUsmSecretEntry.name + (4,) + tblIdx2, "destroy"),)
    )

    # Commit plain-text pass-phrases if we have them

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((pysnmpUsmSecretEntry.name + (4,) + tblIdx2, "createAndGo"),)
    )

    if authKeyType < usmKeyTypeMaster:
        snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
            (
                (pysnmpUsmSecretEntry.name + (1,) + tblIdx2, userName),
                (pysnmpUsmSecretEntry.name + (2,) + tblIdx2, authKey),
            )
        )

    if privKeyType < usmKeyTypeMaster:
        snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
            (
                (pysnmpUsmSecretEntry.name + (1,) + tblIdx2, userName),
                (pysnmpUsmSecretEntry.name + (3,) + tblIdx2, privKey),
            )
        )

    debug.logger & debug.flagSM and debug.logger(
        "addV3User: added new table entries "
        'userName "%s" securityName "%s" authProtocol %s '
        'privProtocol %s localAuthKey "%s" localPrivKey "%s" '
        'masterAuthKey "%s" masterPrivKey "%s" authKey "%s" '
        'privKey "%s" by index securityName "%s" securityEngineId '
        '"%s"'
        % (
            userName,
            securityName,
            authProtocol,
            privProtocol,
            localAuthKey and localAuthKey.prettyPrint(),
            localPrivKey and localPrivKey.prettyPrint(),
            masterAuthKey and masterAuthKey.prettyPrint(),
            masterPrivKey and masterPrivKey.prettyPrint(),
            authKey and authKey.prettyPrint(),
            privKey and privKey.prettyPrint(),
            securityName,
            securityEngineId.prettyPrint(),
        )
    )


def delV3User(
    snmpEngine: Any,
    userName: Any,
    securityEngineId: Any | None = None,
    # deprecated parameters follow
    contextEngineId: Any | None = None,
) -> None:
    if securityEngineId is None:  # backward compatibility
        securityEngineId = contextEngineId
    (securityEngineId, usmUserEntry, tblIdx1, pysnmpUsmSecretEntry, tblIdx2) = __cookV3UserInfo(
        snmpEngine, userName, securityEngineId
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((usmUserEntry.name + (13,) + tblIdx1, "destroy"),)
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((pysnmpUsmSecretEntry.name + (4,) + tblIdx2, "destroy"),)
    )

    debug.logger & debug.flagSM and debug.logger(
        "delV3User: deleted table entries by index "
        'userName "%s" securityEngineId '
        '"%s"' % (debug.prettify(userName), securityEngineId.prettyPrint())
    )

    # Drop all derived rows
    varBinds = initialVarBinds = (
        (usmUserEntry.name + (1,), None),  # usmUserEngineID
        (usmUserEntry.name + (2,), None),  # usmUserName
        (usmUserEntry.name + (4,), None),  # usmUserCloneFrom
    )

    while varBinds:
        varBinds = snmpEngine.msgAndPduDsp.mibInstrumController.readNextVars(varBinds)
        if varBinds[0][1].isSameTypeWith(rfc1905.endOfMibView):
            break
        if varBinds[0][0][: len(initialVarBinds[0][0])] != initialVarBinds[0][0]:
            break
        elif varBinds[2][1] == tblIdx1:  # cloned from this entry
            delV3User(snmpEngine, varBinds[1][1], varBinds[0][1])
            varBinds = initialVarBinds


def __cookTargetParamsInfo(snmpEngine: Any, name: str) -> tuple[Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (snmpTargetParamsEntry,) = mibBuilder.importSymbols("SNMP-TARGET-MIB", "snmpTargetParamsEntry")
    tblIdx = snmpTargetParamsEntry.getInstIdFromIndices(name)
    return snmpTargetParamsEntry, tblIdx


# mpModel: 0 == SNMPv1, 1 == SNMPv2c, 3 == SNMPv3
def addTargetParams(
    snmpEngine: Any,
    name: str,
    securityName: Any,
    securityLevel: int,
    mpModel: int = 3,
) -> None:
    if mpModel == 0:
        securityModel = 1
    elif mpModel in (1, 2):
        securityModel = 2
    elif mpModel == 3:
        securityModel = 3
    else:
        raise error.PySnmpError("Unknown MP model %s" % mpModel)

    snmpTargetParamsEntry, tblIdx = __cookTargetParamsInfo(snmpEngine, name)

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpTargetParamsEntry.name + (7,) + tblIdx, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (snmpTargetParamsEntry.name + (1,) + tblIdx, name),
            (snmpTargetParamsEntry.name + (2,) + tblIdx, mpModel),
            (snmpTargetParamsEntry.name + (3,) + tblIdx, securityModel),
            (snmpTargetParamsEntry.name + (4,) + tblIdx, securityName),
            (snmpTargetParamsEntry.name + (5,) + tblIdx, securityLevel),
            (snmpTargetParamsEntry.name + (7,) + tblIdx, "createAndGo"),
        )
    )


def delTargetParams(snmpEngine: Any, name: str) -> None:
    snmpTargetParamsEntry, tblIdx = __cookTargetParamsInfo(snmpEngine, name)
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpTargetParamsEntry.name + (7,) + tblIdx, "destroy"),)
    )


def __cookTargetAddrInfo(snmpEngine: Any, addrName: str) -> tuple[Any, Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (snmpTargetAddrEntry,) = mibBuilder.importSymbols("SNMP-TARGET-MIB", "snmpTargetAddrEntry")
    (snmpSourceAddrEntry,) = mibBuilder.importSymbols("PYSNMP-SOURCE-MIB", "snmpSourceAddrEntry")
    tblIdx = snmpTargetAddrEntry.getInstIdFromIndices(addrName)
    return snmpTargetAddrEntry, snmpSourceAddrEntry, tblIdx


def addTargetAddr(
    snmpEngine: Any,
    addrName: str,
    transportDomain: Any,
    transportAddress: Any,
    params: str,
    timeout: Any | None = None,
    retryCount: Any | None = None,
    tagList: Any = b"",
    sourceAddress: Any | None = None,
) -> None:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (snmpTargetAddrEntry, snmpSourceAddrEntry, tblIdx) = __cookTargetAddrInfo(snmpEngine, addrName)

    if transportDomain[: len(snmpUDPDomain)] == snmpUDPDomain:
        (SnmpUDPAddress,) = mibBuilder.importSymbols("SNMPv2-TM", "SnmpUDPAddress")
        transportAddress = SnmpUDPAddress(transportAddress)
        if sourceAddress is None:
            sourceAddress = ("0.0.0.0", 0)
        sourceAddress = SnmpUDPAddress(sourceAddress)
    elif transportDomain[: len(snmpUDP6Domain)] == snmpUDP6Domain:
        (TransportAddressIPv6,) = mibBuilder.importSymbols(
            "TRANSPORT-ADDRESS-MIB", "TransportAddressIPv6"
        )
        transportAddress = TransportAddressIPv6(transportAddress)
        if sourceAddress is None:
            sourceAddress = ("::", 0)
        sourceAddress = TransportAddressIPv6(sourceAddress)

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpTargetAddrEntry.name + (9,) + tblIdx, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (snmpTargetAddrEntry.name + (1,) + tblIdx, addrName),
            (snmpTargetAddrEntry.name + (2,) + tblIdx, transportDomain),
            (snmpTargetAddrEntry.name + (3,) + tblIdx, transportAddress),
            (snmpTargetAddrEntry.name + (4,) + tblIdx, timeout),
            (snmpTargetAddrEntry.name + (5,) + tblIdx, retryCount),
            (snmpTargetAddrEntry.name + (6,) + tblIdx, tagList),
            (snmpTargetAddrEntry.name + (7,) + tblIdx, params),
            (snmpSourceAddrEntry.name + (1,) + tblIdx, sourceAddress),
            (snmpTargetAddrEntry.name + (9,) + tblIdx, "createAndGo"),
        )
    )


def delTargetAddr(snmpEngine: Any, addrName: str) -> None:
    (snmpTargetAddrEntry, snmpSourceAddrEntry, tblIdx) = __cookTargetAddrInfo(snmpEngine, addrName)
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpTargetAddrEntry.name + (9,) + tblIdx, "destroy"),)
    )


def addTransport(snmpEngine: Any, transportDomain: Any, transport: Any) -> None:
    if snmpEngine.transportDispatcher:
        if not transport.isCompatibleWithDispatcher(snmpEngine.transportDispatcher):
            raise error.PySnmpError(
                f"Transport {transport!r} is not compatible with dispatcher {snmpEngine.transportDispatcher!r}"
            )
    else:
        dispatcherArgs = {}
        if hasattr(transport, "loop"):
            dispatcherArgs["loop"] = transport.loop
        snmpEngine.registerTransportDispatcher(
            transport.protoTransportDispatcher(**dispatcherArgs)
        )
        # here we note that we have created transportDispatcher automatically
        snmpEngine.setUserContext(automaticTransportDispatcher=0)

    snmpEngine.transportDispatcher.registerTransport(transportDomain, transport)
    automaticTransportDispatcher = snmpEngine.getUserContext("automaticTransportDispatcher")
    if automaticTransportDispatcher is not None:
        snmpEngine.setUserContext(automaticTransportDispatcher=automaticTransportDispatcher + 1)


def getTransport(snmpEngine: Any, transportDomain: Any) -> Any:
    if not snmpEngine.transportDispatcher:
        return
    try:
        return snmpEngine.transportDispatcher.getTransport(transportDomain)
    except error.PySnmpError:
        return


def delTransport(snmpEngine: Any, transportDomain: Any) -> Any:
    if not snmpEngine.transportDispatcher:
        return
    transport = getTransport(snmpEngine, transportDomain)
    snmpEngine.transportDispatcher.unregisterTransport(transportDomain)
    # automatically shutdown automatically created transportDispatcher
    automaticTransportDispatcher = snmpEngine.getUserContext("automaticTransportDispatcher")
    if automaticTransportDispatcher is not None:
        automaticTransportDispatcher -= 1
        snmpEngine.setUserContext(automaticTransportDispatcher=automaticTransportDispatcher)
        if not automaticTransportDispatcher:
            snmpEngine.transportDispatcher.closeDispatcher()
            snmpEngine.unregisterTransportDispatcher()
            snmpEngine.delUserContext(automaticTransportDispatcher)
    return transport


addSocketTransport = addTransport
delSocketTransport = delTransport


# VACM shortcuts


def __cookVacmContextInfo(snmpEngine: Any, contextName: Any) -> tuple[Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder
    (vacmContextEntry,) = mibBuilder.importSymbols("SNMP-VIEW-BASED-ACM-MIB", "vacmContextEntry")
    tblIdx = vacmContextEntry.getInstIdFromIndices(contextName)
    return vacmContextEntry, tblIdx


def addContext(snmpEngine: Any, contextName: Any) -> None:
    vacmContextEntry, tblIdx = __cookVacmContextInfo(snmpEngine, contextName)

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmContextEntry.name + (2,) + tblIdx, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (vacmContextEntry.name + (1,) + tblIdx, contextName),
            (vacmContextEntry.name + (2,) + tblIdx, "createAndGo"),
        )
    )


def delContext(snmpEngine: Any, contextName: Any) -> None:
    vacmContextEntry, tblIdx = __cookVacmContextInfo(snmpEngine, contextName)

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmContextEntry.name + (2,) + tblIdx, "destroy"),)
    )


def __cookVacmGroupInfo(snmpEngine: Any, securityModel: int, securityName: Any) -> tuple[Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (vacmSecurityToGroupEntry,) = mibBuilder.importSymbols(
        "SNMP-VIEW-BASED-ACM-MIB", "vacmSecurityToGroupEntry"
    )
    tblIdx = vacmSecurityToGroupEntry.getInstIdFromIndices(securityModel, securityName)
    return vacmSecurityToGroupEntry, tblIdx


def addVacmGroup(snmpEngine: Any, groupName: str, securityModel: int, securityName: Any) -> None:
    (vacmSecurityToGroupEntry, tblIdx) = __cookVacmGroupInfo(
        snmpEngine, securityModel, securityName
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmSecurityToGroupEntry.name + (5,) + tblIdx, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (vacmSecurityToGroupEntry.name + (1,) + tblIdx, securityModel),
            (vacmSecurityToGroupEntry.name + (2,) + tblIdx, securityName),
            (vacmSecurityToGroupEntry.name + (3,) + tblIdx, groupName),
            (vacmSecurityToGroupEntry.name + (5,) + tblIdx, "createAndGo"),
        )
    )


def delVacmGroup(snmpEngine: Any, securityModel: int, securityName: Any) -> None:
    vacmSecurityToGroupEntry, tblIdx = __cookVacmGroupInfo(snmpEngine, securityModel, securityName)
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmSecurityToGroupEntry.name + (5,) + tblIdx, "destroy"),)
    )


def __cookVacmAccessInfo(
    snmpEngine: Any,
    groupName: str,
    contextName: Any,
    securityModel: int,
    securityLevel: int,
) -> tuple[Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (vacmAccessEntry,) = mibBuilder.importSymbols("SNMP-VIEW-BASED-ACM-MIB", "vacmAccessEntry")
    tblIdx = vacmAccessEntry.getInstIdFromIndices(
        groupName, contextName, securityModel, securityLevel
    )
    return vacmAccessEntry, tblIdx


def addVacmAccess(
    snmpEngine: Any,
    groupName: str,
    contextPrefix: str,
    securityModel: int,
    securityLevel: int,
    contextMatch: Any,
    readView: Any,
    writeView: Any,
    notifyView: Any,
) -> None:
    vacmAccessEntry, tblIdx = __cookVacmAccessInfo(
        snmpEngine, groupName, contextPrefix, securityModel, securityLevel
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmAccessEntry.name + (9,) + tblIdx, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (vacmAccessEntry.name + (1,) + tblIdx, contextPrefix),
            (vacmAccessEntry.name + (2,) + tblIdx, securityModel),
            (vacmAccessEntry.name + (3,) + tblIdx, securityLevel),
            (vacmAccessEntry.name + (4,) + tblIdx, contextMatch),
            (vacmAccessEntry.name + (5,) + tblIdx, readView),
            (vacmAccessEntry.name + (6,) + tblIdx, writeView),
            (vacmAccessEntry.name + (7,) + tblIdx, notifyView),
            (vacmAccessEntry.name + (9,) + tblIdx, "createAndGo"),
        )
    )


def delVacmAccess(
    snmpEngine: Any,
    groupName: str,
    contextPrefix: str,
    securityModel: int,
    securityLevel: int,
) -> None:
    vacmAccessEntry, tblIdx = __cookVacmAccessInfo(
        snmpEngine, groupName, contextPrefix, securityModel, securityLevel
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmAccessEntry.name + (9,) + tblIdx, "destroy"),)
    )


def __cookVacmViewInfo(snmpEngine: Any, viewName: str, subTree: Any) -> tuple[Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (vacmViewTreeFamilyEntry,) = mibBuilder.importSymbols(
        "SNMP-VIEW-BASED-ACM-MIB", "vacmViewTreeFamilyEntry"
    )
    tblIdx = vacmViewTreeFamilyEntry.getInstIdFromIndices(viewName, subTree)
    return vacmViewTreeFamilyEntry, tblIdx


def addVacmView(
    snmpEngine: Any, viewName: str, viewType: str, subTree: Any, subTreeMask: Any
) -> None:
    vacmViewTreeFamilyEntry, tblIdx = __cookVacmViewInfo(snmpEngine, viewName, subTree)

    # Allow bitmask specification in form of an OID
    if rfc1902.OctetString(".").asOctets() in rfc1902.OctetString(subTreeMask):
        subTreeMask = rfc1902.ObjectIdentifier(subTreeMask)

    if isinstance(subTreeMask, rfc1902.ObjectIdentifier):
        subTreeMask = tuple(subTreeMask)
        if len(subTreeMask) < len(subTree):
            subTreeMask += (1,) * (len(subTree) - len(subTreeMask))

        subTreeMask = rfc1902.OctetString.fromBinaryString("".join(str(x) for x in subTreeMask))

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmViewTreeFamilyEntry.name + (6,) + tblIdx, "destroy"),)
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (vacmViewTreeFamilyEntry.name + (1,) + tblIdx, viewName),
            (vacmViewTreeFamilyEntry.name + (2,) + tblIdx, subTree),
            (vacmViewTreeFamilyEntry.name + (3,) + tblIdx, subTreeMask),
            (vacmViewTreeFamilyEntry.name + (4,) + tblIdx, viewType),
            (vacmViewTreeFamilyEntry.name + (6,) + tblIdx, "createAndGo"),
        )
    )


def delVacmView(snmpEngine: Any, viewName: str, subTree: Any) -> None:
    vacmViewTreeFamilyEntry, tblIdx = __cookVacmViewInfo(snmpEngine, viewName, subTree)
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((vacmViewTreeFamilyEntry.name + (6,) + tblIdx, "destroy"),)
    )


# VACM simplicity wrappers


def __cookVacmUserInfo(
    snmpEngine: Any, securityModel: int, securityName: Any, securityLevel: int
) -> tuple[Any, Any, Any, Any, Any]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    groupName = "v-%s-%d" % (hash(securityName), securityModel)
    (SnmpSecurityLevel,) = mibBuilder.importSymbols("SNMP-FRAMEWORK-MIB", "SnmpSecurityLevel")
    securityLevel = SnmpSecurityLevel(securityLevel)
    return (groupName, securityLevel, "r" + groupName, "w" + groupName, "n" + groupName)


def addVacmUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    readSubTree: Any = (),
    writeSubTree: Any = (),
    notifySubTree: Any = (),
    contextName: Any = b"",
) -> None:
    (groupName, securityLevel, readView, writeView, notifyView) = __cookVacmUserInfo(
        snmpEngine, securityModel, securityName, securityLevel
    )
    addContext(snmpEngine, contextName)
    addVacmGroup(snmpEngine, groupName, securityModel, securityName)
    addVacmAccess(
        snmpEngine,
        groupName,
        contextName,
        securityModel,
        securityLevel,
        "exact",
        readView,
        writeView,
        notifyView,
    )
    if readSubTree:
        addVacmView(snmpEngine, readView, "included", readSubTree, b"")
    if writeSubTree:
        addVacmView(snmpEngine, writeView, "included", writeSubTree, b"")
    if notifySubTree:
        addVacmView(snmpEngine, notifyView, "included", notifySubTree, b"")


def delVacmUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    readSubTree: Any = (),
    writeSubTree: Any = (),
    notifySubTree: Any = (),
    contextName: Any = b"",
) -> None:
    (groupName, securityLevel, readView, writeView, notifyView) = __cookVacmUserInfo(
        snmpEngine, securityModel, securityName, securityLevel
    )
    delContext(snmpEngine, contextName)
    delVacmGroup(snmpEngine, securityModel, securityName)
    delVacmAccess(snmpEngine, groupName, contextName, securityModel, securityLevel)
    if readSubTree:
        delVacmView(snmpEngine, readView, readSubTree)
    if writeSubTree:
        delVacmView(snmpEngine, writeView, writeSubTree)
    if notifySubTree:
        delVacmView(snmpEngine, notifyView, notifySubTree)


# Obsolete shortcuts for add/delVacmUser() wrappers


def addRoUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    subTree: Any,
    contextName: Any = b"",
) -> None:
    addVacmUser(
        snmpEngine, securityModel, securityName, securityLevel, subTree, contextName=contextName
    )


def delRoUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    subTree: Any,
    contextName: Any = b"",
) -> None:
    delVacmUser(
        snmpEngine, securityModel, securityName, securityLevel, subTree, contextName=contextName
    )


def addRwUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    subTree: Any,
    contextName: Any = b"",
) -> None:
    addVacmUser(
        snmpEngine,
        securityModel,
        securityName,
        securityLevel,
        subTree,
        subTree,
        contextName=contextName,
    )


def delRwUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    subTree: Any,
    contextName: Any = b"",
) -> None:
    delVacmUser(
        snmpEngine,
        securityModel,
        securityName,
        securityLevel,
        subTree,
        subTree,
        contextName=contextName,
    )


def addTrapUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    subTree: Any,
    contextName: Any = b"",
) -> None:
    addVacmUser(
        snmpEngine,
        securityModel,
        securityName,
        securityLevel,
        (),
        (),
        subTree,
        contextName=contextName,
    )


def delTrapUser(
    snmpEngine: Any,
    securityModel: int,
    securityName: Any,
    securityLevel: int,
    subTree: Any,
    contextName: Any = b"",
) -> None:
    delVacmUser(
        snmpEngine,
        securityModel,
        securityName,
        securityLevel,
        (),
        (),
        subTree,
        contextName=contextName,
    )


# Notification target setup


def __cookNotificationTargetInfo(
    snmpEngine: Any,
    notificationName: str,
    paramsName: str,
    filterSubtree: Any | None = None,
    filterProfileName: Any | None = None,
) -> tuple[Any, ...]:
    mibBuilder = snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder

    (snmpNotifyEntry,) = mibBuilder.importSymbols("SNMP-NOTIFICATION-MIB", "snmpNotifyEntry")
    tblIdx1 = snmpNotifyEntry.getInstIdFromIndices(notificationName)

    (snmpNotifyFilterProfileEntry,) = mibBuilder.importSymbols(
        "SNMP-NOTIFICATION-MIB", "snmpNotifyFilterProfileEntry"
    )
    tblIdx2 = snmpNotifyFilterProfileEntry.getInstIdFromIndices(paramsName)

    profileName = (
        filterProfileName
        if filterProfileName is not None
        else "%s-filter" % hash(notificationName)
    )

    if filterSubtree:
        (snmpNotifyFilterEntry,) = mibBuilder.importSymbols(
            "SNMP-NOTIFICATION-MIB", "snmpNotifyFilterEntry"
        )
        tblIdx3 = snmpNotifyFilterEntry.getInstIdFromIndices(profileName, filterSubtree)
    else:
        snmpNotifyFilterEntry = tblIdx3 = None

    return (
        snmpNotifyEntry,
        tblIdx1,
        snmpNotifyFilterProfileEntry,
        tblIdx2,
        profileName,
        snmpNotifyFilterEntry,
        tblIdx3,
    )


def addNotificationTarget(
    snmpEngine: Any,
    notificationName: str,
    paramsName: str,
    transportTag: Any,
    notifyType: Any | None = None,
    filterSubtree: Any | None = None,
    filterMask: Any | None = None,
    filterType: Any | None = None,
    filterProfileName: Any | None = None,
) -> None:
    (
        snmpNotifyEntry,
        tblIdx1,
        snmpNotifyFilterProfileEntry,
        tblIdx2,
        profileName,
        snmpNotifyFilterEntry,
        tblIdx3,
    ) = __cookNotificationTargetInfo(
        snmpEngine,
        notificationName,
        paramsName,
        filterSubtree,
        filterProfileName,
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpNotifyEntry.name + (5,) + tblIdx1, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (snmpNotifyEntry.name + (2,) + tblIdx1, transportTag),
            (snmpNotifyEntry.name + (3,) + tblIdx1, notifyType),
            (snmpNotifyEntry.name + (5,) + tblIdx1, "createAndGo"),
        )
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpNotifyFilterProfileEntry.name + (3,) + tblIdx2, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (snmpNotifyFilterProfileEntry.name + (1,) + tblIdx2, profileName),
            (snmpNotifyFilterProfileEntry.name + (3,) + tblIdx2, "createAndGo"),
        )
    )

    if not snmpNotifyFilterEntry:
        return

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpNotifyFilterEntry.name + (5,) + tblIdx3, "destroy"),)
    )
    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (snmpNotifyFilterEntry.name + (1,) + tblIdx3, filterSubtree),
            (snmpNotifyFilterEntry.name + (2,) + tblIdx3, filterMask),
            (snmpNotifyFilterEntry.name + (3,) + tblIdx3, filterType),
            (snmpNotifyFilterEntry.name + (5,) + tblIdx3, "createAndGo"),
        )
    )


def delNotificationTarget(
    snmpEngine: Any,
    notificationName: str,
    paramsName: str,
    filterSubtree: Any | None = None,
    filterProfileName: Any | None = None,
) -> None:
    (
        snmpNotifyEntry,
        tblIdx1,
        snmpNotifyFilterProfileEntry,
        tblIdx2,
        profileName,
        snmpNotifyFilterEntry,
        tblIdx3,
    ) = __cookNotificationTargetInfo(
        snmpEngine,
        notificationName,
        paramsName,
        filterSubtree,
        filterProfileName,
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpNotifyEntry.name + (5,) + tblIdx1, "destroy"),)
    )

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpNotifyFilterProfileEntry.name + (3,) + tblIdx2, "destroy"),)
    )

    if not snmpNotifyFilterEntry:
        return

    snmpEngine.msgAndPduDsp.mibInstrumController.writeVars(
        ((snmpNotifyFilterEntry.name + (5,) + tblIdx3, "destroy"),)
    )


# rfc3415: A.1
def setInitialVacmParameters(snmpEngine: Any) -> None:
    # rfc3415: A.1.1 --> initial-semi-security-configuration

    # rfc3415: A.1.2
    addContext(snmpEngine, "")

    # rfc3415: A.1.3
    addVacmGroup(snmpEngine, "initial", 3, "initial")

    # rfc3415: A.1.4
    # securityLevel: 1=noAuthNoPriv, 2=authNoPriv, 3=authPriv (SnmpSecurityLevel)
    addVacmAccess(snmpEngine, "initial", "", 3, 1, "exact", "restricted", None, "restricted")
    addVacmAccess(snmpEngine, "initial", "", 3, 2, "exact", "internet", "internet", "internet")
    addVacmAccess(snmpEngine, "initial", "", 3, 3, "exact", "internet", "internet", "internet")

    # rfc3415: A.1.5 (semi-secure)
    addVacmView(snmpEngine, "internet", "included", (1, 3, 6, 1), "")
    # Exclude USM objects from SNMP access for security (Phase 3.6)
    addVacmView(snmpEngine, "internet", "excluded", (1, 3, 6, 1, 6, 3, 15), "")
    # Exclude SNMP-COMMUNITY-MIB from SNMP access for security (Phase 3.8)
    addVacmView(snmpEngine, "internet", "excluded", (1, 3, 6, 1, 6, 3, 18), "")
    addVacmView(snmpEngine, "restricted", "included", (1, 3, 6, 1, 2, 1, 1), "")
    addVacmView(snmpEngine, "restricted", "included", (1, 3, 6, 1, 2, 1, 11), "")
    addVacmView(snmpEngine, "restricted", "included", (1, 3, 6, 1, 6, 3, 10, 2, 1), "")
    addVacmView(snmpEngine, "restricted", "included", (1, 3, 6, 1, 6, 3, 11, 2, 1), "")
    addVacmView(snmpEngine, "restricted", "included", (1, 3, 6, 1, 6, 3, 15, 1, 1), "")
