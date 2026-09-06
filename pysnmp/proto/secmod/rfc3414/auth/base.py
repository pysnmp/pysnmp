#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
from pysnmp.proto import errind, error


class AbstractAuthenticationService:
    #: OID naming the protocol this service implements, e.g. usmHMACMD5AuthProtocol.
    #: Concrete services differ in length, so the arity cannot be pinned here.
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
