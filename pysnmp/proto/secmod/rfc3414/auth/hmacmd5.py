#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""HMAC-MD5-96 authentication.

MD5 is no longer considered safe; RFC 7860's SHA-2 protocols are the
replacement. Configuring this raises `PySnmpWeakCryptoWarning`.
"""

from hashlib import md5

from pyasn1.type import univ

from pysnmp.proto import errind, error
from pysnmp.proto.secmod.rfc3414 import localkey
from pysnmp.proto.secmod.rfc3414.auth import base

_twelveZeros = univ.OctetString((0,) * 12).asOctets()
_fortyEightZeros = (0,) * 48


# rfc3414: 6.2.4


class HmacMd5(base.AbstractAuthenticationService):
    """HMAC-MD5-96. Broken; use `HmacSha2` instead."""

    serviceID: tuple[int, ...] = (
        1,
        3,
        6,
        1,
        6,
        3,
        10,
        1,
        1,
        2,
    )  # usmHMACMD5AuthProtocol
    __ipad = [0x36] * 64
    __opad = [0x5C] * 64

    def hashPassphrase(self, authKey):
        """Hash a passphrase into a master key with MD5."""
        return localkey.hashPassphraseMD5(authKey)

    def localizeKey(self, authKey, snmpEngineID):
        """Bind a master key to one engine ID, so it cannot be replayed at another."""
        return localkey.localizeKeyMD5(authKey, snmpEngineID)

    @property
    def digestLength(self):
        """12 -- HMAC-MD5-96 is truncated to 96 bits."""
        return 12

    # 6.3.1
    def authenticateOutgoingMsg(self, authKey, wholeMsg):
        # Here we expect calling secmod to indicate where the digest
        # should be in the substrate. Also, it pre-sets digest placeholder
        # so we hash wholeMsg out of the box.
        # Yes, that's ugly but that's rfc...
        """Compute HMAC-MD5-96 over the message and write it into the placeholder.

        The caller has already serialized the message with twelve zero octets where
        the digest goes, because the digest covers the whole message including its own
        field. Finding that run of zeros is how the position is recovered.
        """
        idx = wholeMsg.find(_twelveZeros)
        if idx == -1:
            raise error.ProtocolError("Cant locate digest placeholder")
        wholeHead = wholeMsg[:idx]
        wholeTail = wholeMsg[idx + 12 :]

        # 6.3.1.1

        # 6.3.1.2a
        extendedAuthKey = authKey.asNumbers() + _fortyEightZeros

        # 6.3.1.2b --> no-op

        # 6.3.1.2c
        k1 = univ.OctetString(map(lambda x, y: x ^ y, extendedAuthKey, self.__ipad))

        # 6.3.1.2d --> no-op

        # 6.3.1.2e
        k2 = univ.OctetString(map(lambda x, y: x ^ y, extendedAuthKey, self.__opad))

        # 6.3.1.3
        # noinspection PyDeprecation,PyCallingNonCallable
        d1 = md5(k1.asOctets() + wholeMsg).digest()

        # 6.3.1.4
        # noinspection PyDeprecation,PyCallingNonCallable
        d2 = md5(k2.asOctets() + d1).digest()
        mac = d2[:12]

        # 6.3.1.5 & 6
        return wholeHead + mac + wholeTail

    # 6.3.2
    def authenticateIncomingMsg(self, authKey, authParameters, wholeMsg):
        # 6.3.2.1 & 2
        """Check HMAC-MD5-96, zeroing the digest field before recomputing.

        The sender hashed the message with zeros in the digest field, so the same
        substitution has to be made here before the two can be compared.
        """
        if len(authParameters) != 12:
            raise error.StatusInformation(errorIndication=errind.authenticationError)

        # 6.3.2.3
        idx = wholeMsg.find(authParameters.asOctets())
        if idx == -1:
            raise error.ProtocolError("Cant locate digest in wholeMsg")
        wholeHead = wholeMsg[:idx]
        wholeTail = wholeMsg[idx + 12 :]
        authenticatedWholeMsg = wholeHead + _twelveZeros + wholeTail

        # 6.3.2.4a
        extendedAuthKey = authKey.asNumbers() + _fortyEightZeros

        # 6.3.2.4b --> no-op

        # 6.3.2.4c
        k1 = univ.OctetString(map(lambda x, y: x ^ y, extendedAuthKey, self.__ipad))

        # 6.3.2.4d --> no-op

        # 6.3.2.4e
        k2 = univ.OctetString(map(lambda x, y: x ^ y, extendedAuthKey, self.__opad))

        # 6.3.2.5a
        # noinspection PyDeprecation,PyCallingNonCallable
        d1 = md5(k1.asOctets() + authenticatedWholeMsg).digest()

        # 6.3.2.5b
        # noinspection PyDeprecation,PyCallingNonCallable
        d2 = md5(k2.asOctets() + d1).digest()

        # 6.3.2.5c
        mac = d2[:12]

        # 6.3.2.6
        if mac != authParameters:
            raise error.StatusInformation(errorIndication=errind.authenticationFailure)

        return authenticatedWholeMsg
