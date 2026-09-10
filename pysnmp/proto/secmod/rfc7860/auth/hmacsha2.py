#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2018, Olivier Verriest <verri@x25.pm>
#
"""HMAC-SHA-2 authentication at 224, 256, 384 and 512 bits, per RFC 7860."""

import hmac
from hashlib import sha224, sha256, sha384, sha512

from pyasn1.type import univ

from pysnmp.proto import errind, error
from pysnmp.proto.secmod.rfc3414 import localkey
from pysnmp.proto.secmod.rfc3414.auth import base

# 7.2.4


class HmacSha2(base.AbstractAuthenticationService):
    """HMAC-SHA-2, at 224, 256, 384 or 512 bits.

    One class for all four: `serviceID` picks which, and the hash, key length and
    digest length follow from it.
    """

    sha224ServiceID = (1, 3, 6, 1, 6, 3, 10, 1, 1, 4)  # usmHMAC128SHA224AuthProtocol
    sha256ServiceID = (1, 3, 6, 1, 6, 3, 10, 1, 1, 5)  # usmHMAC192SHA256AuthProtocol
    sha384ServiceID = (1, 3, 6, 1, 6, 3, 10, 1, 1, 6)  # usmHMAC256SHA384AuthProtocol
    sha512ServiceID = (1, 3, 6, 1, 6, 3, 10, 1, 1, 7)  # usmHMAC384SHA512AuthProtocol
    keyLengths = {
        sha224ServiceID: 28,
        sha256ServiceID: 32,
        sha384ServiceID: 48,
        sha512ServiceID: 64,
    }
    digestLengths = {
        sha224ServiceID: 16,
        sha256ServiceID: 24,
        sha384ServiceID: 32,
        sha512ServiceID: 48,
    }
    hashAlgorithms = {
        sha224ServiceID: sha224,
        sha256ServiceID: sha256,
        sha384ServiceID: sha384,
        sha512ServiceID: sha512,
    }

    def __init__(self, oid):
        """Selects the SHA-2 variant the protocol OID names.

        The four variants differ in digest length and in how much of the digest goes on
        the wire (:RFC:`7860#section-4`), so both are looked up here and an OID for a
        variant this does not implement is refused at construction rather than at first
        use.
        """
        if oid not in self.hashAlgorithms:
            raise error.ProtocolError(
                f"No SHA-2 authentication algorithm {oid} available"
            )
        self.__hashAlgo = self.hashAlgorithms[oid]
        self.__digestLength = self.digestLengths[oid]
        self.__placeHolder = univ.OctetString((0,) * self.__digestLength).asOctets()

    def hashPassphrase(self, authKey):
        """Hash a passphrase into a master key with this instance's SHA-2 variant."""
        return localkey.hashPassphrase(authKey, self.__hashAlgo)

    def localizeKey(self, authKey, snmpEngineID):
        """Bind a master key to one engine ID, so it cannot be replayed at another."""
        return localkey.localizeKey(authKey, snmpEngineID, self.__hashAlgo)

    @property
    def digestLength(self):
        """Octets of digest, which differs per SHA-2 variant -- 16 for SHA-224 up to 48."""
        return self.__digestLength

    # 7.3.1
    def authenticateOutgoingMsg(self, authKey, wholeMsg):
        # 7.3.1.1
        """Compute the HMAC and write it into the placeholder.

        Unlike the :RFC:`3414` services the placeholder is not always twelve octets,
        so its length comes from the variant in use.
        """
        location = wholeMsg.find(self.__placeHolder)
        if location == -1:
            raise error.ProtocolError("Can't locate digest placeholder")
        wholeHead = wholeMsg[:location]
        wholeTail = wholeMsg[location + self.__digestLength :]

        # 7.3.1.2, 7.3.1.3
        try:
            mac = hmac.new(authKey.asOctets(), wholeMsg, self.__hashAlgo)

        except errind.ErrorIndication as e:
            raise error.StatusInformation(errorIndication=e) from e

        # 7.3.1.4
        mac = mac.digest()[: self.__digestLength]

        # 7.3.1.5 & 6
        return wholeHead + mac + wholeTail

    # 7.3.2
    def authenticateIncomingMsg(self, authKey, authParameters, wholeMsg):
        # 7.3.2.1 & 2
        """Check the HMAC, zeroing the digest field before recomputing."""
        if len(authParameters) != self.__digestLength:
            raise error.StatusInformation(errorIndication=errind.authenticationError)

        # 7.3.2.3
        location = wholeMsg.find(authParameters.asOctets())
        if location == -1:
            raise error.ProtocolError("Can't locate digest in wholeMsg")
        wholeHead = wholeMsg[:location]
        wholeTail = wholeMsg[location + self.__digestLength :]
        authenticatedWholeMsg = wholeHead + self.__placeHolder + wholeTail

        # 7.3.2.4
        try:
            mac = hmac.new(authKey.asOctets(), authenticatedWholeMsg, self.__hashAlgo)

        except errind.ErrorIndication as e:
            raise error.StatusInformation(errorIndication=e) from e

        # 7.3.2.5
        mac = mac.digest()[: self.__digestLength]

        # 7.3.2.6
        if mac != authParameters:
            raise error.StatusInformation(errorIndication=errind.authenticationFailure)

        return authenticatedWholeMsg
