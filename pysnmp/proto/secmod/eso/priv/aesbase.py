#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Extending a localized key to the length AES-192 and AES-256 need.

RFC 3826 localizes a key to the digest length, which is shorter than these
ciphers take. Blumenthal and Reeder each specified a way to stretch it, and
they do not agree, so a peer has to be matched on which one it implements.
"""

from hashlib import md5, sha1
from math import ceil

from pysnmp.proto import error
from pysnmp.proto.secmod.rfc3414 import localkey
from pysnmp.proto.secmod.rfc3414.auth import hmacmd5, hmacsha
from pysnmp.proto.secmod.rfc3826.priv import aes
from pysnmp.proto.secmod.rfc7860.auth import hmacsha2


class AbstractAesBlumenthal(aes.Aes):
    """AES with a key extended the way Blumenthal's draft says.

    AES-192 and AES-256 need more key material than a localized key provides, and
    the two drafts that extend it disagree. This one runs the localization
    function again over the previous output, chaining until the key is long
    enough. A peer implementing Reeder's variant will not interoperate.
    """

    serviceID: tuple[int, ...] = ()
    keySize = 0

    # 3.1.2.1
    def localizeKey(self, authProtocol, privKey, snmpEngineID):
        """Localize, then chain the hash over its own output until the key is long enough.

        AES-192 and AES-256 need more key material than one localization produces.
        Blumenthal's draft extends it by hashing the result again and appending, which
        is what this does; Reeder's variant does something else, and the two do not
        interoperate.
        """
        if authProtocol == hmacmd5.HmacMd5.serviceID:
            hashAlgo = md5
        elif authProtocol == hmacsha.HmacSha.serviceID:
            hashAlgo = sha1
        elif authProtocol in hmacsha2.HmacSha2.hashAlgorithms:
            hashAlgo = hmacsha2.HmacSha2.hashAlgorithms[authProtocol]
        else:
            raise error.ProtocolError(f"Unknown auth protocol {authProtocol}")

        localPrivKey = localkey.localizeKey(privKey, snmpEngineID, hashAlgo)

        # now extend this key if too short by repeating steps that includes the hashPassphrase step
        for count in range(1, ceil(self.keySize * 1.0 / len(localPrivKey))):
            localPrivKey += localPrivKey.clone(
                hashAlgo(localPrivKey.asOctets()).digest()
            )

        return localPrivKey[: self.keySize]


class AbstractAesReeder(aes.Aes):
    """AES encryption with non-standard key localization.

    Many vendors (including Cisco) do not use:

    https://datatracker.ietf.org/doc/html/draft-blumenthal-aes-usm-04

    for key localization instead, they use the procedure for 3DES key localization
    specified in:

    https://datatracker.ietf.org/doc/html/draft-reeder-snmpv3-usm-3desede-00

    The difference between the two is that the Reeder draft does key extension by repeating
    the steps in the password to key algorithm (hash phrase, then localize with SNMPEngine ID).
    """

    serviceID: tuple[int, ...] = ()
    keySize = 0

    # 2.1 of https://datatracker.ietf.org/doc/html/draft-blumenthal-aes-usm-04
    def localizeKey(self, authProtocol, privKey, snmpEngineID):
        """Localize by re-running the passphrase hash, as Reeder's draft has it.

        The difference from Blumenthal is where the extension comes from: this repeats
        the password-to-key step rather than hashing the localized key. Cisco and
        others implement this one.
        """
        if authProtocol == hmacmd5.HmacMd5.serviceID:
            hashAlgo = md5
        elif authProtocol == hmacsha.HmacSha.serviceID:
            hashAlgo = sha1
        elif authProtocol in hmacsha2.HmacSha2.hashAlgorithms:
            hashAlgo = hmacsha2.HmacSha2.hashAlgorithms[authProtocol]
        else:
            raise error.ProtocolError(f"Unknown auth protocol {authProtocol}")

        localPrivKey = localkey.localizeKey(privKey, snmpEngineID, hashAlgo)

        # now extend this key if too short by repeating steps that includes the hashPassphrase step
        while len(localPrivKey) < self.keySize:
            # this is the difference between reeder and bluementhal
            newKey = localkey.hashPassphrase(localPrivKey, hashAlgo)
            localPrivKey += localkey.localizeKey(newKey, snmpEngineID, hashAlgo)

        return localPrivKey[: self.keySize]
