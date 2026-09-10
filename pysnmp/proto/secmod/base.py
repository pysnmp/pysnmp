#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""What a security model has to provide."""

from pysnmp.proto import error
from pysnmp.proto.secmod import cache


class AbstractSecurityModel:
    """Authenticates and encrypts a message, and undoes both on the way in.

    Which model is `securityModelID`. Maps between the security name an
    application uses and whatever credential the wire format carries, and holds
    the state linking a request to the response that answers it.
    """

    #: securityModel value this model answers to (:RFC:`3411#section-4`), e.g. 3
    #: for USM. None until a concrete model names one.
    securityModelID: int | None = None

    def __init__(self):
        """Each model instance gets its own cache of in-flight requests."""
        self._cache = cache.Cache()

    def processIncomingMsg(
        self,
        snmpEngine,
        messageProcessingModel,
        maxMessageSize,
        securityParameters,
        securityModel,
        securityLevel,
        wholeMsg,
        msg,
    ):
        raise error.ProtocolError(f"Security model {self} not implemented")

    def generateRequestMsg(
        self,
        snmpEngine,
        messageProcessingModel,
        globalData,
        maxMessageSize,
        securityModel,
        securityEngineID,
        securityName,
        securityLevel,
        scopedPDU,
    ):
        raise error.ProtocolError(f"Security model {self} not implemented")

    def generateResponseMsg(
        self,
        snmpEngine,
        messageProcessingModel,
        globalData,
        maxMessageSize,
        securityModel,
        securityEngineID,
        securityName,
        securityLevel,
        scopedPDU,
        securityStateReference,
    ):
        raise error.ProtocolError(f"Security model {self} not implemented")

    def releaseStateInformation(self, stateReference):
        self._cache.pop(stateReference)

    def receiveTimerTick(self, snmpEngine, timeNow):
        # Security models without timers do not need to take action.
        pass
