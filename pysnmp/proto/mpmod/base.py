#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""What a message processing model has to provide."""

from typing import Any

from pysnmp.proto import error
from pysnmp.proto.mpmod import cache


class AbstractMessageProcessingModel:
    #: ASN.1 class of the message this model speaks; __init__ instantiates it.
    #: NotImplementedError stands in for a model that has not named one -- it is
    #: constructed, not raised, so the failure surfaces later rather than here.
    """Turns a PDU into a message and back, for one SNMP version.

    Which version is `messageProcessingModelID`. The model decides what the
    header looks like and which security model handles it, and holds the state
    linking an outgoing request to the response that answers it.
    """

    snmpMsgSpec: type[Any] = NotImplementedError

    def __init__(self):
        self._snmpMsgSpec = self.snmpMsgSpec()  # local copy
        self._cache = cache.Cache()

    def prepareOutgoingMessage(
        self,
        snmpEngine,
        transportDomain,
        transportAddress,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineId,
        contextName,
        pduVersion,
        pdu,
        expectResponse,
        sendPduHandle,
    ):
        raise error.ProtocolError("method not implemented")

    def prepareResponseMessage(
        self,
        snmpEngine,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineId,
        contextName,
        pduVersion,
        pdu,
        maxSizeResponseScopedPDU,
        stateReference,
        statusInformation,
    ):
        raise error.ProtocolError("method not implemented")

    def prepareDataElements(
        self, snmpEngine, transportDomain, transportAddress, wholeMsg
    ):
        raise error.ProtocolError("method not implemented")

    def releaseStateInformation(self, sendPduHandle):
        try:
            self._cache.popBySendPduHandle(sendPduHandle)
        except error.ProtocolError:
            pass  # XXX maybe these should all follow some scheme?

    def receiveTimerTick(self, snmpEngine, timeNow):
        self._cache.expireCaches()
