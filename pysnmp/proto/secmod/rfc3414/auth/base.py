#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""What an authentication service has to provide."""

from pysnmp.proto import errind, error


class AbstractAuthenticationService:
    """Computes and checks the digest that authenticates a message.

    A passphrase is hashed once, then localized to each engine it is used with, so
    the key on the wire differs per engine and a key learned from one does not
    open another.
    """

    #: OID naming the protocol this service implements, e.g. usmHMACMD5AuthProtocol.
    #: Concrete services differ in length, so the arity cannot be pinned here.
    serviceID: tuple[int, ...] | None = None

    def hashPassphrase(self, authKey):
        """Hash a passphrase into a master key. Concrete services implement this."""
        raise error.ProtocolError(errind.noAuthentication)

    def localizeKey(self, authKey, snmpEngineID):
        """Bind a master key to one engine ID. Concrete services implement this."""
        raise error.ProtocolError(errind.noAuthentication)

    @property
    def digestLength(self):
        """Octets of digest this service puts in the message."""
        raise error.ProtocolError(errind.noAuthentication)

    # 7.2.4.1
    def authenticateOutgoingMsg(self, authKey, wholeMsg):
        """Fill in the digest placeholder. Concrete services implement this."""
        raise error.ProtocolError(errind.noAuthentication)

    # 7.2.4.2
    def authenticateIncomingMsg(self, authKey, authParameters, wholeMsg):
        """Check the digest. Concrete services implement this."""
        raise error.ProtocolError(errind.noAuthentication)
