#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""What an encryption service has to provide."""

from pysnmp.proto import error


class AbstractEncryptionService:
    """Encrypts and decrypts the scoped PDU.

    Keys are derived and localized as for authentication; `keySize` says how much
    key material the cipher needs, which is what decides whether a localized key
    has to be extended first.
    """

    #: OID naming the protocol this service implements, e.g. usmDESPrivProtocol.
    #: Concrete services differ in length, so the arity cannot be pinned here.
    serviceID: tuple[int, ...] | None = None
    keySize = 0

    def hashPassphrase(self, authProtocol, privKey):
        raise error.ProtocolError("no encryption")

    def localizeKey(self, authProtocol, privKey, snmpEngineID):
        raise error.ProtocolError("no encryption")

    def encryptData(self, encryptKey, privParameters, dataToEncrypt):
        raise error.ProtocolError("no encryption")

    def decryptData(self, decryptKey, privParameters, encryptedData):
        raise error.ProtocolError("no encryption")
