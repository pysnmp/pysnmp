#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""What an authentication service has to provide."""

from pysnmp.proto import errind, error


class AbstractAuthenticationService:
    #: OID naming the protocol this service implements, e.g. usmHMACMD5AuthProtocol.
    #: Concrete services differ in length, so the arity cannot be pinned here.
    """Computes and checks the digest that authenticates a message.

    A passphrase is hashed once, then localized to each engine it is used with, so
    the key on the wire differs per engine and a key learned from one does not
    open another.
    """

    serviceID: tuple[int, ...] | None = None

    def hashPassphrase(self, authKey):
        raise error.ProtocolError(errind.noAuthentication)

    def localizeKey(self, authKey, snmpEngineID):
        raise error.ProtocolError(errind.noAuthentication)

    @property
    def digestLength(self):
        raise error.ProtocolError(errind.noAuthentication)

    # 7.2.4.1
    def authenticateOutgoingMsg(self, authKey, wholeMsg):
        raise error.ProtocolError(errind.noAuthentication)

    # 7.2.4.2
    def authenticateIncomingMsg(self, authKey, authParameters, wholeMsg):
        raise error.ProtocolError(errind.noAuthentication)
