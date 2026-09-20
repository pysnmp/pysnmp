#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""The message and PDU dispatcher: the middle of the engine.

Everything inbound and outbound passes through here. It picks the message
processing model for the version, routes a PDU to whichever application
registered for it, and matches responses to the requests waiting on them.
"""

from inspect import isawaitable

from pyasn1.error import PyAsn1Error

from pysnmp import debug, nextid
from pysnmp.entity.observer import execution_context
from pysnmp.error import PySnmpError
from pysnmp.proto import cache, errind, error
from pysnmp.proto.api import verdec  # XXX
from pysnmp.smi import builder, instrum


def _sameTransportAddress(cachedAddress, transportAddress):
    """Whether two transport addresses name the same peer.

    Compared by value rather than by identity or type: the same peer reaches the
    request cache as whatever the target address table produced -- a MIB object,
    often -- and reaches a transport as that transport's own address type.
    """
    if cachedAddress is None:
        return False

    try:
        return tuple(cachedAddress) == tuple(transportAddress)

    except TypeError:
        # An address shape that is not a sequence at all, such as the
        # filesystem path a Unix-domain transport is named by.
        return cachedAddress == transportAddress


class MsgAndPduDispatcher:
    """SNMP engine PDU & message dispatcher.

    Exchanges SNMP PDU's with applications and serialized messages with
    transport level.
    """

    def __init__(self, mibInstrumController=None):
        """Creates MIB instrumentation if none is given, and loads what the engine needs.

        The modules loaded here are the ones the engine itself reads and writes during
        normal operation -- its counters, its USM and VACM tables -- so they are not
        optional and are not left to the application to remember.
        """
        if mibInstrumController is None:
            self.mibInstrumController = instrum.MibInstrumController(
                builder.MibBuilder()
            )
        else:
            self.mibInstrumController = mibInstrumController

        self.mibInstrumController.mibBuilder.loadModules(
            "SNMPv2-MIB",
            "SNMP-MPD-MIB",
            "SNMP-COMMUNITY-MIB",
            "SNMP-TARGET-MIB",
            "SNMP-USER-BASED-SM-MIB",
        )

        # Requests cache
        self.__cache = cache.Cache()

        # Registered context engine IDs
        self.__appsRegistration = {}

        # Source of sendPduHandle and cache of requesting apps
        self.__sendPduHandle = nextid.Integer(0xFFFFFF)

        # To pass transport info to app (legacy)
        self.__transportInfo = {}

    # legacy
    def getTransportInfo(self, stateReference):
        """Where a request came from, so a response can be sent back to it."""
        if stateReference in self.__transportInfo:
            return self.__transportInfo[stateReference]
        else:
            raise error.ProtocolError(f"No data for stateReference {stateReference}")

    # Application registration with dispatcher

    # 4.3.1
    def registerContextEngineId(self, contextEngineId, pduTypes, processPdu):
        """Register application with dispatcher."""
        # 4.3.2 -> no-op

        # 4.3.3
        for pduType in pduTypes:
            k = (contextEngineId, pduType)
            if k in self.__appsRegistration:
                raise error.ProtocolError(
                    f"Duplicate registration {contextEngineId!r}/{pduType}"
                )

            # 4.3.4
            self.__appsRegistration[k] = processPdu

        debug.logger & debug.flagDsp and debug.logger(
            f"registerContextEngineId: contextEngineId {contextEngineId!r} pduTypes {pduTypes}"
        )

    # 4.4.1
    def unregisterContextEngineId(self, contextEngineId, pduTypes):
        """Unregister application with dispatcher."""
        # 4.3.4
        if contextEngineId is None:
            # Default to local snmpEngineId
            (contextEngineId,) = self.mibInstrumController.mibBuilder.importSymbols(
                "__SNMP-FRAMEWORK-MIB", "snmpEngineID"
            )

        for pduType in pduTypes:
            k = (contextEngineId, pduType)
            if k in self.__appsRegistration:
                del self.__appsRegistration[k]

        debug.logger & debug.flagDsp and debug.logger(
            f"unregisterContextEngineId: contextEngineId {contextEngineId!r} pduTypes {pduTypes}"
        )

    def getRegisteredApp(self, contextEngineId, pduType):
        """The application registered for a context and PDU type, wildcard included.

        An exact registration wins; failing that the empty context engine ID matches
        anything, which is how a notification receiver takes traps from engines it has
        never heard of.
        """
        k = (contextEngineId, pduType)
        if k in self.__appsRegistration:
            return self.__appsRegistration[k]
        k = (b"", pduType)
        if k in self.__appsRegistration:
            return self.__appsRegistration[k]  # wildcard

    # Dispatcher <-> application API

    # 4.1.1

    def sendPdu(
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
        PDU,
        expectResponse,
        timeout=0,
        cbFun=None,
        cbCtx=None,
    ):
        """PDU dispatcher -- prepare and serialize a request or notification."""
        # 4.1.1.2
        k = int(messageProcessingModel)
        if k in snmpEngine.messageProcessingSubsystems:
            mpHandler = snmpEngine.messageProcessingSubsystems[k]
        else:
            raise error.StatusInformation(
                errorIndication=errind.unsupportedMsgProcessingModel
            )

        debug.logger & debug.flagDsp and debug.logger(
            f"sendPdu: securityName {debug.prettify(securityName)}, PDU\n{PDU.prettyPrint()}"
        )

        # 4.1.1.3
        sendPduHandle = self.__sendPduHandle()
        if expectResponse:
            self.__cache.add(
                sendPduHandle,
                messageProcessingModel=messageProcessingModel,
                sendPduHandle=sendPduHandle,
                timeout=timeout + snmpEngine.transportDispatcher.getTimerTicks(),
                cbFun=cbFun,
                cbCtx=cbCtx,
            )

            debug.logger & debug.flagDsp and debug.logger(
                f"sendPdu: current time "
                f"{snmpEngine.transportDispatcher.getTimerTicks()} ticks, one tick "
                f"is {snmpEngine.transportDispatcher.getTimerResolution()} seconds"
            )

        debug.logger & debug.flagDsp and debug.logger(
            f"sendPdu: new sendPduHandle {sendPduHandle}, timeout {timeout} ticks, cbFun {cbFun}"
        )

        origTransportDomain = transportDomain
        origTransportAddress = transportAddress

        # 4.1.1.4 & 4.1.1.5
        try:
            (transportDomain, transportAddress, outgoingMessage) = (
                mpHandler.prepareOutgoingMessage(
                    snmpEngine,
                    origTransportDomain,
                    origTransportAddress,
                    messageProcessingModel,
                    securityModel,
                    securityName,
                    securityLevel,
                    contextEngineId,
                    contextName,
                    pduVersion,
                    PDU,
                    expectResponse,
                    sendPduHandle,
                )
            )

            debug.logger & debug.flagDsp and debug.logger("sendPdu: MP succeeded")
        except PySnmpError:
            if expectResponse:
                self.__cache.pop(sendPduHandle)
                self.releaseStateInformation(
                    snmpEngine, sendPduHandle, messageProcessingModel
                )
            raise

        # 4.1.1.6
        if snmpEngine.transportDispatcher is None:
            if expectResponse:
                self.__cache.pop(sendPduHandle)

            raise error.PySnmpError("Transport dispatcher not set")

        with execution_context(
            snmpEngine,
            "rfc3412.sendPdu",
            transportDomain=transportDomain,
            transportAddress=transportAddress,
            outgoingMessage=outgoingMessage,
            messageProcessingModel=messageProcessingModel,
            securityModel=securityModel,
            securityName=securityName,
            securityLevel=securityLevel,
            contextEngineId=contextEngineId,
            contextName=contextName,
            pdu=PDU,
        ):
            try:
                snmpEngine.transportDispatcher.sendMessage(
                    outgoingMessage, transportDomain, transportAddress
                )
            except PySnmpError:
                if expectResponse:
                    self.__cache.pop(sendPduHandle)
                raise

        # Update cache with orignal req params (used for retrying)
        if expectResponse:
            self.__cache.update(
                sendPduHandle,
                transportDomain=origTransportDomain,
                transportAddress=origTransportAddress,
                securityModel=securityModel,
                securityName=securityName,
                securityLevel=securityLevel,
                contextEngineId=contextEngineId,
                contextName=contextName,
                pduVersion=pduVersion,
                PDU=PDU,
            )

        return sendPduHandle

    # 4.1.2.1
    def returnResponsePdu(
        self,
        snmpEngine,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineId,
        contextName,
        pduVersion,
        PDU,
        maxSizeResponseScopedPDU,
        stateReference,
        statusInformation,
    ):
        # Extract input values and initialize defaults
        """Send an application's response back out through the model it arrived on."""
        k = int(messageProcessingModel)
        if k in snmpEngine.messageProcessingSubsystems:
            mpHandler = snmpEngine.messageProcessingSubsystems[k]
        else:
            raise error.StatusInformation(
                errorIndication=errind.unsupportedMsgProcessingModel
            )

        debug.logger & debug.flagDsp and debug.logger(
            "returnResponsePdu: PDU {}".format(PDU and PDU.prettyPrint() or "<empty>")
        )

        # 4.1.2.2. A StatusInformation raised here propagates unchanged
        # (:RFC:`3412#section-4.1.2.3`).
        (transportDomain, transportAddress, outgoingMessage) = (
            mpHandler.prepareResponseMessage(
                snmpEngine,
                messageProcessingModel,
                securityModel,
                securityName,
                securityLevel,
                contextEngineId,
                contextName,
                pduVersion,
                PDU,
                maxSizeResponseScopedPDU,
                stateReference,
                statusInformation,
            )
        )

        debug.logger & debug.flagDsp and debug.logger("returnResponsePdu: MP suceeded")

        # Handle oversized messages XXX transport constrains?
        (snmpEngineMaxMessageSize,) = (
            self.mibInstrumController.mibBuilder.importSymbols(
                "__SNMP-FRAMEWORK-MIB", "snmpEngineMaxMessageSize"
            )
        )
        if (
            snmpEngineMaxMessageSize.syntax
            and len(outgoingMessage) > snmpEngineMaxMessageSize.syntax
        ):
            (snmpSilentDrops,) = self.mibInstrumController.mibBuilder.importSymbols(
                "__SNMPv2-MIB", "snmpSilentDrops"
            )
            snmpSilentDrops.syntax += 1
            raise error.StatusInformation(errorIndication=errind.tooBig)

        with execution_context(
            snmpEngine,
            "rfc3412.returnResponsePdu",
            transportDomain=transportDomain,
            transportAddress=transportAddress,
            outgoingMessage=outgoingMessage,
            messageProcessingModel=messageProcessingModel,
            securityModel=securityModel,
            securityName=securityName,
            securityLevel=securityLevel,
            contextEngineId=contextEngineId,
            contextName=contextName,
            pdu=PDU,
        ):
            # 4.1.2.4
            snmpEngine.transportDispatcher.sendMessage(
                outgoingMessage, transportDomain, transportAddress
            )

    def __deferRequest(self, snmpEngine, awaitable, execpointVars, stateReference):
        """Hand the rest of a suspended request to the dispatcher to finish.

        Nothing here can wait for it: this call is on the loop, and waiting would
        be waiting on the loop that has to run the work. A dispatcher that cannot
        run a task says so, and the request fails rather than being dropped
        silently with the requester left to time out.
        """
        coro = self.__completeRequest(
            snmpEngine, awaitable, execpointVars, stateReference
        )

        transportDispatcher = snmpEngine.transportDispatcher

        if transportDispatcher is None:
            self.__abandonRequest(coro, awaitable, stateReference)
            raise PySnmpError(
                "Instrumentation suspended while serving a request, but this "
                "engine has no transport dispatcher to finish it on"
            )

        try:
            transportDispatcher.runDeferred(coro)

        except BaseException:
            self.__abandonRequest(coro, awaitable, stateReference)
            raise

    def __abandonRequest(self, coro, awaitable, stateReference):
        """Drop work that could not be handed off, leaving nothing half-open.

        Both the continuation and whatever the application was waiting on are
        closed here: neither has been started, and a coroutine left unstarted is
        reported by asyncio as one that was never awaited.
        """
        coro.close()

        close = getattr(awaitable, "close", None)
        if close is not None:
            close()

        if stateReference is not None:
            self.__transportInfo.pop(stateReference, None)

    async def __completeRequest(
        self, snmpEngine, awaitable, execpointVars, stateReference
    ):
        """Wait out a suspended request, with its own state around it again.

        The execution point and the transport info are entered again here rather
        than held open across the suspension. Both answer the question "which
        request is being served", and the engine serves others while this one
        waits -- so they are restored for as long as this request is running and
        dropped again when it is done, which is what keeps access control
        reading this requester's identity and not the last one to arrive.
        """
        with execution_context(
            snmpEngine, "rfc3412.receiveMessage:request", execpointVars
        ):
            if stateReference is not None:
                self.__transportInfo[stateReference] = (
                    execpointVars["transportDomain"],
                    execpointVars["transportAddress"],
                )
            try:
                await awaitable
            finally:
                if stateReference is not None:
                    self.__transportInfo.pop(stateReference, None)

    # 4.2.1
    def receiveMessage(self, snmpEngine, transportDomain, transportAddress, wholeMsg):
        """Message dispatcher -- de-serialize message into PDU."""
        # 4.2.1.1
        (snmpInPkts,) = self.mibInstrumController.mibBuilder.importSymbols(
            "__SNMPv2-MIB", "snmpInPkts"
        )
        snmpInPkts.syntax += 1

        # 4.2.1.2
        try:
            restOfWholeMsg = b""  # XXX fix decoder non-recursive return
            msgVersion = verdec.decodeMessageVersion(wholeMsg)

        except error.ProtocolError:
            (snmpInASNParseErrs,) = self.mibInstrumController.mibBuilder.importSymbols(
                "__SNMPv2-MIB", "snmpInASNParseErrs"
            )
            snmpInASNParseErrs.syntax += 1
            return b""  # n.b the whole buffer gets dropped

        debug.logger & debug.flagDsp and debug.logger(
            f"receiveMessage: msgVersion {msgVersion}, msg decoded"
        )

        messageProcessingModel = msgVersion

        try:
            mpHandler = snmpEngine.messageProcessingSubsystems[
                int(messageProcessingModel)
            ]

        except KeyError:
            (snmpInBadVersions,) = self.mibInstrumController.mibBuilder.importSymbols(
                "__SNMPv2-MIB", "snmpInBadVersions"
            )
            snmpInBadVersions.syntax += 1
            return restOfWholeMsg

        # 4.2.1.3 -- no-op

        # 4.2.1.4
        try:
            (
                messageProcessingModel,
                securityModel,
                securityName,
                securityLevel,
                contextEngineId,
                contextName,
                pduVersion,
                PDU,
                pduType,
                sendPduHandle,
                maxSizeResponseScopedPDU,
                statusInformation,
                stateReference,
            ) = mpHandler.prepareDataElements(
                snmpEngine, transportDomain, transportAddress, wholeMsg
            )

            debug.logger & debug.flagDsp and debug.logger("receiveMessage: MP succeded")

        except error.StatusInformation as mpError:
            if "sendPduHandle" in mpError:
                # Dropped REPORT -- re-run pending reqs queue as some
                # of them may be waiting for this REPORT
                debug.logger & debug.flagDsp and debug.logger(
                    f"receiveMessage: MP failed, statusInformation {mpError}, forcing a retry"
                )
                self.__expireRequest(
                    mpError["sendPduHandle"],
                    self.__cache.pop(mpError["sendPduHandle"]),
                    snmpEngine,
                    mpError,
                )
            return restOfWholeMsg

        except PyAsn1Error as e:
            debug.logger & debug.flagMP and debug.logger(f"receiveMessage: {e}")
            (snmpInASNParseErrs,) = (
                snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                    "__SNMPv2-MIB", "snmpInASNParseErrs"
                )
            )
            snmpInASNParseErrs.syntax += 1

            return restOfWholeMsg

        debug.logger & debug.flagDsp and debug.logger(
            f"receiveMessage: PDU {PDU.prettyPrint()}"
        )

        # 4.2.2
        if sendPduHandle is None:
            # 4.2.2.1 (request or notification)

            debug.logger & debug.flagDsp and debug.logger(
                f"receiveMessage: pduType {pduType}"
            )
            # 4.2.2.1.1
            processPdu = self.getRegisteredApp(contextEngineId, pduType)

            # 4.2.2.1.2
            if processPdu is None:
                # 4.2.2.1.2.a
                (snmpUnknownPDUHandlers,) = (
                    self.mibInstrumController.mibBuilder.importSymbols(
                        "__SNMP-MPD-MIB", "snmpUnknownPDUHandlers"
                    )
                )
                snmpUnknownPDUHandlers.syntax += 1

                # 4.2.2.1.2.b
                statusInformation = {
                    "errorIndication": errind.unknownPDUHandler,
                    "oid": snmpUnknownPDUHandlers.name,
                    "val": snmpUnknownPDUHandlers.syntax,
                }

                debug.logger & debug.flagDsp and debug.logger(
                    "receiveMessage: unhandled PDU type"
                )

                # 4.2.2.1.2.c
                try:
                    (destTransportDomain, destTransportAddress, outgoingMessage) = (
                        mpHandler.prepareResponseMessage(
                            snmpEngine,
                            messageProcessingModel,
                            securityModel,
                            securityName,
                            securityLevel,
                            contextEngineId,
                            contextName,
                            pduVersion,
                            PDU,
                            maxSizeResponseScopedPDU,
                            stateReference,
                            statusInformation,
                        )
                    )

                    snmpEngine.transportDispatcher.sendMessage(
                        outgoingMessage, destTransportDomain, destTransportAddress
                    )

                except PySnmpError as e:
                    debug.logger & debug.flagDsp and debug.logger(
                        f"receiveMessage: report failed, statusInformation {e}"
                    )

                else:
                    debug.logger & debug.flagDsp and debug.logger(
                        "receiveMessage: reporting succeeded"
                    )

                # 4.2.2.1.2.d
                return restOfWholeMsg

            else:
                execpointVars = {
                    "transportDomain": transportDomain,
                    "transportAddress": transportAddress,
                    "wholeMsg": wholeMsg,
                    "messageProcessingModel": messageProcessingModel,
                    "securityModel": securityModel,
                    "securityName": securityName,
                    "securityLevel": securityLevel,
                    "contextEngineId": contextEngineId,
                    "contextName": contextName,
                    "pdu": PDU,
                }

                deferred = None

                with execution_context(
                    snmpEngine, "rfc3412.receiveMessage:request", execpointVars
                ):
                    # pass transport info to app (legacy)
                    if stateReference is not None:
                        self.__transportInfo[stateReference] = (
                            transportDomain,
                            transportAddress,
                        )

                    try:
                        # 4.2.2.1.3
                        deferred = processPdu(
                            snmpEngine,
                            messageProcessingModel,
                            securityModel,
                            securityName,
                            securityLevel,
                            contextEngineId,
                            contextName,
                            pduVersion,
                            PDU,
                            maxSizeResponseScopedPDU,
                            stateReference,
                        )

                        # An application whose instrumentation is a coroutine
                        # cannot have answered yet; what it hands back is the
                        # rest of the work.
                        if deferred is not None and not isawaitable(deferred):
                            deferred = None
                    except BaseException:
                        deferred = None
                        raise
                    finally:
                        # clear transport info passed to app (legacy), unless the
                        # application still has to answer and will need it
                        if stateReference is not None and deferred is None:
                            del self.__transportInfo[stateReference]

                if deferred is not None:
                    self.__deferRequest(
                        snmpEngine, deferred, execpointVars, stateReference
                    )

                    debug.logger & debug.flagDsp and debug.logger(
                        "receiveMessage: processPdu suspended, deferred"
                    )
                    return restOfWholeMsg

                debug.logger & debug.flagDsp and debug.logger(
                    "receiveMessage: processPdu succeeded"
                )
                return restOfWholeMsg
        else:
            # 4.2.2.2 (response)

            # 4.2.2.2.1
            cachedParams = self.__cache.pop(sendPduHandle)

            # 4.2.2.2.2
            if cachedParams is None:
                (snmpUnknownPDUHandlers,) = (
                    self.mibInstrumController.mibBuilder.importSymbols(
                        "__SNMP-MPD-MIB", "snmpUnknownPDUHandlers"
                    )
                )
                snmpUnknownPDUHandlers.syntax += 1
                return restOfWholeMsg

            debug.logger & debug.flagDsp and debug.logger(
                f"receiveMessage: cache read by sendPduHandle {sendPduHandle}"
            )

            # 4.2.2.2.3
            # no-op ? XXX

            with execution_context(
                snmpEngine,
                "rfc3412.receiveMessage:response",
                transportDomain=transportDomain,
                transportAddress=transportAddress,
                wholeMsg=wholeMsg,
                messageProcessingModel=messageProcessingModel,
                securityModel=securityModel,
                securityName=securityName,
                securityLevel=securityLevel,
                contextEngineId=contextEngineId,
                contextName=contextName,
                pdu=PDU,
            ):
                # 4.2.2.2.4
                processResponsePdu = cachedParams["cbFun"]

                processResponsePdu(
                    snmpEngine,
                    messageProcessingModel,
                    securityModel,
                    securityName,
                    securityLevel,
                    contextEngineId,
                    contextName,
                    pduVersion,
                    PDU,
                    statusInformation,
                    cachedParams["sendPduHandle"],
                    cachedParams["cbCtx"],
                )

            debug.logger & debug.flagDsp and debug.logger(
                "receiveMessage: processResponsePdu succeeded"
            )

            return restOfWholeMsg

    def releaseStateInformation(
        self, snmpEngine, sendPduHandle, messageProcessingModel
    ):
        """Drop what was held for a request, in the dispatcher and the model both."""
        k = int(messageProcessingModel)
        if k in snmpEngine.messageProcessingSubsystems:
            mpHandler = snmpEngine.messageProcessingSubsystems[k]
            mpHandler.releaseStateInformation(sendPduHandle)

        self.__cache.pop(sendPduHandle)

    # Cache expiration stuff

    # noinspection PyUnusedLocal
    def __expireRequest(
        self, cacheKey, cachedParams, snmpEngine, statusInformation=None
    ):
        timeNow = snmpEngine.transportDispatcher.getTimerTicks()
        timeoutAt = cachedParams["timeout"]

        if statusInformation is None and timeNow < timeoutAt:
            return

        processResponsePdu = cachedParams["cbFun"]

        debug.logger & debug.flagDsp and debug.logger(
            f"__expireRequest: req cachedParams {cachedParams}"
        )

        # Fail timed-out requests
        if not statusInformation:
            statusInformation = error.StatusInformation(
                errorIndication=errind.requestTimedOut
            )

        self.releaseStateInformation(
            snmpEngine,
            cachedParams["sendPduHandle"],
            cachedParams["messageProcessingModel"],
        )

        processResponsePdu(
            snmpEngine,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            statusInformation,
            cachedParams["sendPduHandle"],
            cachedParams["cbCtx"],
        )
        return True

    def receiveTransportError(
        self, snmpEngine, transportDomain, transportAddress, transportError
    ):
        """Fail every outstanding request bound for an address the transport lost.

        The transport reports this when it learns a peer cannot be reached -- a
        refused or unanswered TCP connection -- which a datagram transport never
        can. Failing the requests now is the whole point: they would otherwise sit
        through their full retry schedule to arrive at `requestTimedOut`, which
        says something weaker and says it much later.

        Requests to other peers on the same transport are untouched: one stream
        carrier serves every peer of its domain, and only this one failed.
        """
        statusInformation = error.StatusInformation(
            errorIndication=errind.TransportFailure(str(transportError))
        )

        def failMatchingRequest(cacheKey, cachedParams, snmpEngine):
            if cachedParams.get("transportDomain") != transportDomain:
                return None

            if not _sameTransportAddress(
                cachedParams.get("transportAddress"), transportAddress
            ):
                return None

            debug.logger & debug.flagDsp and debug.logger(
                f"receiveTransportError: failing request to {transportAddress!r}: "
                f"{transportError}"
            )

            return self.__expireRequest(
                cacheKey, cachedParams, snmpEngine, statusInformation
            )

        self.__cache.expire(failMatchingRequest, snmpEngine)

    # noinspection PyUnusedLocal
    def receiveTimerTick(self, snmpEngine, timeNow):
        """Expire requests that were never answered, reporting a timeout for each."""
        self.__cache.expire(self.__expireRequest, snmpEngine)
