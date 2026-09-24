#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The absence of privacy, as a service the model can call."""

from pysnmp.proto import errind, error
from pysnmp.proto.secmod.rfc3414.priv import base


class NoPriv(base.AbstractEncryptionService):
    """No privacy: leaves the scoped PDU in the clear."""

    serviceID: tuple[int, ...] = (1, 3, 6, 1, 6, 3, 10, 1, 2, 1)  # usmNoPrivProtocol

    def hashPassphrase(self, authProtocol, privKey):
        """Nothing to hash: there is no privacy key at this security level."""
        return

    def localizeKey(self, authProtocol, privKey, snmpEngineID):
        """Nothing to localize: there is no privacy key at this security level."""
        return

    def encryptData(self, encryptKey, privParameters, dataToEncrypt):
        """Always fails -- asking to encrypt with no privacy is a mistake."""
        raise error.StatusInformation(errorIndication=errind.noEncryption)

    def decryptData(self, decryptKey, privParameters, encryptedData):
        """Always fails, for the same reason as the outgoing side."""
        raise error.StatusInformation(errorIndication=errind.noEncryption)
