#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""The command responder: the agent side that answers requests from the MIB."""

from inspect import isawaitable

from pyasn1.type import tag

import pysnmp.smi.error
from pysnmp import debug
from pysnmp.proto import errind, error, rfc1902, rfc1905, rfc3411
from pysnmp.proto.api import v2c  # backend is always SMIv2 compliant
from pysnmp.proto.proxy import rfc2576
from pysnmp.smi._instrumcompat import awaitInstrumentation, callInstrumentation


# 3.2
class CommandResponderBase:
    """Answers a request out of the MIB, subject to access control.

    A responder registers for the PDU types it handles, checks every variable
    binding against the view the requester is allowed to see, and turns a MIB
    error into the error status and index the version in use can express -- which
    is not the same set for v1 as for v2c.
    """

    acmID = 3  # default MIB access control method to use
    #: PDU tag sets this responder registers for; each subclass names its own.
    pduTypes: tuple[tag.TagSet, ...] = ()

    def __init__(self, snmpEngine, snmpContext):
        """Registers this responder for its PDU types under the context engine ID."""
        snmpEngine.msgAndPduDsp.registerContextEngineId(
            snmpContext.contextEngineId, self.pduTypes, self.processPdu
        )
        self.snmpContext = snmpContext
        self.__pendingReqs = {}

    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        """Serve one request. Concrete responders implement this.

        An implementation answers before returning, and returns nothing. One
        whose instrumentation has to be waited on cannot answer yet: it returns
        an awaitable instead, and whoever called it sees the request through.
        """
        # Concrete responders implement their management operation here.
        pass

    def close(self, snmpEngine):
        """Deregister from the dispatcher and drop what is still pending."""
        snmpEngine.msgAndPduDsp.unregisterContextEngineId(
            self.snmpContext.contextEngineId, self.pduTypes
        )
        self.snmpContext = self.__pendingReqs = None

    def sendVarBinds(
        self, snmpEngine, stateReference, errorStatus, errorIndex, varBinds
    ):
        """Answer with these bindings and this error status."""
        (
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineId,
            contextName,
            pduVersion,
            PDU,
            origPdu,
            maxSizeResponseScopedPDU,
            statusInformation,
        ) = self.__pendingReqs[stateReference]

        v2c.apiPDU.setErrorStatus(PDU, errorStatus)
        v2c.apiPDU.setErrorIndex(PDU, errorIndex)
        v2c.apiPDU.setVarBinds(PDU, varBinds)

        debug.logger & debug.flagApp and debug.logger(
            f"sendVarBinds: stateReference {stateReference}, errorStatus {errorStatus}, errorIndex {errorIndex}, varBinds {varBinds}"
        )

        self.sendPdu(snmpEngine, stateReference, PDU)

    # backward compatibility
    sendRsp = sendVarBinds

    def sendPdu(self, snmpEngine, stateReference, PDU):
        """Send a prepared response, translating it back to v1 for a v1 peer.

        Everything above this works in SMIv2, so a v1 request is answered by converting
        the v2c response -- the original request coming along because v1 has no way to
        say some of what v2c can, and the translation needs to know what was asked.
        """
        (
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineId,
            contextName,
            pduVersion,
            _,
            origPdu,
            maxSizeResponseScopedPDU,
            statusInformation,
        ) = self.__pendingReqs[stateReference]

        # Agent-side API complies with SMIv2
        if messageProcessingModel == 0:
            PDU = rfc2576.v2ToV1(PDU, origPdu)

        # 3.2.6
        try:
            snmpEngine.msgAndPduDsp.returnResponsePdu(
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

        except error.StatusInformation as e:
            debug.logger & debug.flagApp and debug.logger(
                f"sendPdu: stateReference {stateReference}, statusInformation {e}"
            )
            (snmpSilentDrops,) = (
                snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                    "__SNMPv2-MIB", "snmpSilentDrops"
                )
            )
            snmpSilentDrops.syntax += 1

    _getRequestType = rfc1905.GetRequestPDU.tagSet
    _getNextRequestType = rfc1905.GetNextRequestPDU.tagSet
    _setRequestType = rfc1905.SetRequestPDU.tagSet
    _counter64Type = rfc1902.Counter64.tagSet

    def releaseStateInformation(self, stateReference):
        """Drop what was held for a request. Unknown references are ignored."""
        if stateReference in self.__pendingReqs:
            del self.__pendingReqs[stateReference]

    def processPdu(
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
    ):
        """Take one request, run the operation, and turn any failure into an error status.

        A failure the wire can express is answered rather than raised, since a
        request that produced no response at all would leave the manager waiting
        out its timeout for no reason; :py:meth:`_failedMgmtOperation` does that
        mapping.

        Returns nothing once the request has been answered. An operation whose
        instrumentation has to be waited on cannot answer while this is on the
        stack, and what comes back instead is the rest of the work for the
        dispatcher to run.
        """
        # Agent-side API complies with SMIv2
        if messageProcessingModel == 0:
            origPdu = PDU
            PDU = rfc2576.v1ToV2(PDU)
        else:
            origPdu = None

        # 3.2.1
        if (
            PDU.tagSet not in rfc3411.readClassPDUs
            and PDU.tagSet not in rfc3411.writeClassPDUs
        ):
            raise error.ProtocolError(f"Unexpected PDU class {PDU.tagSet}")

        # 3.2.2 --> no-op

        # 3.2.4
        rspPDU = v2c.apiPDU.getResponse(PDU)

        statusInformation = {}

        self.__pendingReqs[stateReference] = (
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineId,
            contextName,
            pduVersion,
            rspPDU,
            origPdu,
            maxSizeResponseScopedPDU,
            statusInformation,
        )

        # 3.2.5
        varBinds = v2c.apiPDU.getVarBinds(PDU)

        debug.logger & debug.flagApp and debug.logger(
            f"processPdu: stateReference {stateReference}, varBinds {varBinds}"
        )

        try:
            deferred = self.handleMgmtOperation(
                snmpEngine,
                stateReference,
                contextName,
                PDU,
                (self.__verifyAccess, snmpEngine),
            )

        except Exception as exc:  # noqa: BLE001 - a request that answered with nothing leaves the manager to time out, so every failure is mapped to an error status
            self._failedMgmtOperation(
                exc, snmpEngine, stateReference, varBinds, statusInformation
            )
            return None

        # The operation could not answer yet because its instrumentation has to
        # be waited on. What comes back is the rest of the work, which the
        # dispatcher runs; a failure in it lands in the same mapping below.
        if deferred is not None and isawaitable(deferred):
            return self._completeMgmtOperation(
                deferred, snmpEngine, stateReference, varBinds, statusInformation
            )

        return None

    async def _completeMgmtOperation(
        self, awaitable, snmpEngine, stateReference, varBinds, statusInformation
    ):
        """Wait out an operation that suspended, failing it the same way.

        A failure here reaches the requester exactly as one raised while
        :py:meth:`processPdu` was still on the stack does, which is the point:
        waiting is not supposed to change what an error looks like.
        """
        try:
            await awaitable

        except Exception as exc:  # noqa: BLE001 - this is a task of its own, so an escaping exception would be reported to the loop and never to the requester
            self._failedMgmtOperation(
                exc, snmpEngine, stateReference, varBinds, statusInformation
            )

    def _failedMgmtOperation(
        self, exc, snmpEngine, stateReference, varBinds, statusInformation
    ):
        """Turn a failed operation into the error status and index the wire carries.

        The failure is raised again to be caught by name below rather than
        matched against a table of types: the order of the clauses is the
        mapping, since these errors are related to one another, and the one the
        wire wants is the most specific that fits. Raising it is also what lets
        the synchronous path and a suspended one share a single chain.

        Anything the chain does not name propagates, as it did when this ran
        inline in :py:meth:`processPdu`.
        """
        errorStatus, errorIndex = "noError", 0

        try:
            raise exc

        # SNMPv2 SMI exceptions
        except pysnmp.smi.error.GenError as errorIndication:
            debug.logger & debug.flagApp and debug.logger(
                f"processPdu: stateReference {stateReference}, errorIndication {errorIndication}"
            )
            if "oid" in errorIndication:
                # Request REPORT generation
                statusInformation["oid"] = errorIndication["oid"]
                statusInformation["val"] = errorIndication["val"]
            else:
                errorStatus, errorIndex = (
                    "genErr",
                    errorIndication["idx"] + 1 if "idx" in errorIndication else 0,
                )

        # Handle PDU-level SMI errors

        except pysnmp.smi.error.TooBigError:
            errorStatus, errorIndex = "tooBig", 0
            # rfc1905: 4.2.1.3
            varBinds = []

        # this should never bubble up, SNMP exception objects should be passed as values
        except pysnmp.smi.error.NoSuchNameError as e:
            errorStatus, errorIndex = "noSuchName", e["idx"] + 1

        except pysnmp.smi.error.BadValueError as e:
            errorStatus, errorIndex = "badValue", e["idx"] + 1

        except pysnmp.smi.error.ReadOnlyError as e:
            errorStatus, errorIndex = "readOnly", e["idx"] + 1

        except pysnmp.smi.error.NoAccessError as e:
            errorStatus, errorIndex = "noAccess", e["idx"] + 1

        except pysnmp.smi.error.WrongTypeError as e:
            errorStatus, errorIndex = "wrongType", e["idx"] + 1

        except pysnmp.smi.error.WrongLengthError as e:
            errorStatus, errorIndex = "wrongLength", e["idx"] + 1

        except pysnmp.smi.error.WrongEncodingError as e:
            errorStatus, errorIndex = "wrongEncoding", e["idx"] + 1

        except pysnmp.smi.error.WrongValueError as e:
            errorStatus, errorIndex = "wrongValue", e["idx"] + 1

        except pysnmp.smi.error.NoCreationError as e:
            errorStatus, errorIndex = "noCreation", e["idx"] + 1

        except pysnmp.smi.error.InconsistentValueError as e:
            errorStatus, errorIndex = "inconsistentValue", e["idx"] + 1

        except pysnmp.smi.error.ResourceUnavailableError as e:
            errorStatus, errorIndex = "resourceUnavailable", e["idx"] + 1

        except pysnmp.smi.error.CommitFailedError as e:
            errorStatus, errorIndex = "commitFailed", e["idx"] + 1

        except pysnmp.smi.error.UndoFailedError as e:
            errorStatus, errorIndex = "undoFailed", e["idx"] + 1

        except pysnmp.smi.error.AuthorizationError as e:
            errorStatus, errorIndex = "authorizationError", e["idx"] + 1

        except pysnmp.smi.error.NotWritableError as e:
            errorStatus, errorIndex = "notWritable", e["idx"] + 1

        except pysnmp.smi.error.InconsistentNameError as e:
            errorStatus, errorIndex = "inconsistentName", e["idx"] + 1

        except pysnmp.smi.error.SmiError:
            errorStatus, errorIndex = "genErr", len(varBinds) and 1

        except pysnmp.error.PySnmpError:
            self.releaseStateInformation(stateReference)
            return

        self.sendVarBinds(snmpEngine, stateReference, errorStatus, errorIndex, varBinds)

        self.releaseStateInformation(stateReference)

    def __verifyAccess(self, name, syntax, idx, viewType, acCtx):
        """Check one binding against the access control model, as an SMI error.

        The credentials come from the observer's record of the message rather than
        being threaded down through the instrumentation, which never needs them for
        anything else. ACM refusals are mapped to `AuthorizationError`, so an object
        the caller may not see is indistinguishable from one that is not there.
        """
        snmpEngine = acCtx
        execCtx = snmpEngine.observer.getExecutionContext(
            "rfc3412.receiveMessage:request"
        )
        (securityModel, securityName, securityLevel, contextName, pduType) = (
            execCtx["securityModel"],
            execCtx["securityName"],
            execCtx["securityLevel"],
            execCtx["contextName"],
            execCtx["pdu"].tagSet,
        )
        try:
            snmpEngine.accessControlModel[self.acmID].isAccessAllowed(
                snmpEngine,
                securityModel,
                securityName,
                securityLevel,
                viewType,
                contextName,
                name,
            )
        # Map ACM errors onto SMI ones
        except error.StatusInformation as statusInformation:
            debug.logger & debug.flagApp and debug.logger(
                f"__verifyAccess: name {name}, statusInformation {statusInformation}"
            )
            errorIndication = statusInformation["errorIndication"]
            # 3.2.5...
            if errorIndication in (
                errind.noSuchView,
                errind.noAccessEntry,
                errind.noGroupName,
            ):
                raise pysnmp.smi.error.AuthorizationError(
                    name=name, idx=idx
                ) from statusInformation
            elif errorIndication == errind.otherError:
                raise pysnmp.smi.error.GenError(
                    name=name, idx=idx
                ) from statusInformation
            elif errorIndication == errind.noSuchContext:
                (snmpUnknownContexts,) = (
                    snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                        "__SNMP-TARGET-MIB", "snmpUnknownContexts"
                    )
                )
                snmpUnknownContexts.syntax += 1
                # Request REPORT generation
                raise pysnmp.smi.error.GenError(
                    name=name,
                    idx=idx,
                    oid=snmpUnknownContexts.name,
                    val=snmpUnknownContexts.syntax,
                ) from statusInformation
            elif errorIndication == errind.notInView:
                return 1
            else:
                raise error.ProtocolError(
                    f"Unknown ACM error {errorIndication}"
                ) from statusInformation
        else:
            # rfc2576: 4.1.2.1
            if (
                securityModel == 1
                and syntax is not None
                and self._counter64Type == syntax.tagSet
                and self._getNextRequestType == pduType
            ):
                # This will cause MibTree to skip this OID-value
                raise pysnmp.smi.error.NoAccessError(name=name, idx=idx)


class GetCommandResponder(CommandResponderBase):
    """Answers GET."""

    pduTypes = (rfc1905.GetRequestPDU.tagSet,)

    # rfc1905: 4.2.1
    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        """Read exactly the objects named."""
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.1.1
        mgmtFun = self.snmpContext.getMibInstrum(contextName).readVars
        rspVarBinds = callInstrumentation(
            mgmtFun, v2c.apiPDU.getVarBinds(PDU), acFun=acFun, acCtx=acCtx
        )

        if isawaitable(rspVarBinds):
            return self.__answerOnceRead(rspVarBinds, snmpEngine, stateReference)

        self.sendVarBinds(snmpEngine, stateReference, 0, 0, rspVarBinds)
        self.releaseStateInformation(stateReference)

    async def __answerOnceRead(self, awaitable, snmpEngine, stateReference):
        """Answer once instrumentation that had to be waited on has read."""
        self.sendVarBinds(snmpEngine, stateReference, 0, 0, await awaitable)
        self.releaseStateInformation(stateReference)


class NextCommandResponder(CommandResponderBase):
    """Answers GETNEXT."""

    pduTypes = (rfc1905.GetNextRequestPDU.tagSet,)

    # rfc1905: 4.2.2
    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        """Read the objects following those named."""
        (acFun, acCtx) = acInfo
        # rfc1905: 4.2.2.1
        mgmtFun = self.snmpContext.getMibInstrum(contextName).readNextVars
        varBinds = v2c.apiPDU.getVarBinds(PDU)
        while True:
            rspVarBinds = callInstrumentation(
                mgmtFun, varBinds, acFun=acFun, acCtx=acCtx
            )

            if isawaitable(rspVarBinds):
                return self.__answerOnceWalked(
                    rspVarBinds,
                    mgmtFun,
                    varBinds,
                    snmpEngine,
                    stateReference,
                    acFun,
                    acCtx,
                )

            try:
                self.sendVarBinds(snmpEngine, stateReference, 0, 0, rspVarBinds)
            except error.StatusInformation as e:
                idx = e["idx"]
                varBinds[idx] = (rspVarBinds[idx][0], varBinds[idx][1])
            else:
                break
        self.releaseStateInformation(stateReference)

    async def __answerOnceWalked(
        self, rspVarBinds, mgmtFun, varBinds, snmpEngine, stateReference, acFun, acCtx
    ):
        """Finish a walk whose instrumentation had to be waited on.

        This is the loop above, resumed: the read that suspended is already in
        flight when this is entered, and every pass after a binding was dropped
        for being too large to send runs here.
        """
        while True:
            rspVarBinds = await awaitInstrumentation(rspVarBinds)

            try:
                self.sendVarBinds(snmpEngine, stateReference, 0, 0, rspVarBinds)
            except error.StatusInformation as e:
                idx = e["idx"]
                varBinds[idx] = (rspVarBinds[idx][0], varBinds[idx][1])
            else:
                break

            rspVarBinds = callInstrumentation(
                mgmtFun, varBinds, acFun=acFun, acCtx=acCtx
            )

        self.releaseStateInformation(stateReference)


class BulkCommandResponder(CommandResponderBase):
    """Answers GETBULK.

    `maxVarBinds` caps how many bindings one response may carry, since the
    repetition count comes from the requester and is otherwise unbounded.
    """

    pduTypes = (rfc1905.GetBulkRequestPDU.tagSet,)
    maxVarBinds = 64

    # rfc1905: 4.2.3
    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        """Read repeatedly, capping the repetitions at what `maxVarBinds` allows.

        The requester names the repetition count, so without a cap it decides how much
        work the agent does and how large the response gets. :RFC:`3416` lets an agent
        return fewer repetitions than asked for, which is what makes capping legal.
        """
        (acFun, acCtx) = acInfo
        nonRepeaters = v2c.apiBulkPDU.getNonRepeaters(PDU)
        nonRepeaters = max(nonRepeaters, 0)
        maxRepetitions = v2c.apiBulkPDU.getMaxRepetitions(PDU)
        maxRepetitions = max(maxRepetitions, 0)

        reqVarBinds = v2c.apiPDU.getVarBinds(PDU)

        N = min(int(nonRepeaters), len(reqVarBinds))
        M = int(maxRepetitions)
        R = max(len(reqVarBinds) - N, 0)

        if R:
            M = min(M, self.maxVarBinds // R)

        debug.logger & debug.flagApp and debug.logger(
            f"handleMgmtOperation: N {N}, M {M}, R {R}"
        )

        mgmtFun = self.snmpContext.getMibInstrum(contextName).readNextVars

        if N:
            rspVarBinds = callInstrumentation(
                mgmtFun, reqVarBinds[:N], acFun=acFun, acCtx=acCtx
            )

            if isawaitable(rspVarBinds):
                return self.__answerOnceBulkRead(
                    rspVarBinds,
                    [],
                    reqVarBinds[-R:],
                    M,
                    R,
                    mgmtFun,
                    snmpEngine,
                    stateReference,
                    acFun,
                    acCtx,
                )
        else:
            rspVarBinds = []

        varBinds = reqVarBinds[-R:]
        while M and R:
            repetition = callInstrumentation(
                mgmtFun, varBinds, acFun=acFun, acCtx=acCtx
            )

            if isawaitable(repetition):
                # The bindings this repetition reads decide what the next one
                # asks for, so where to carry on from is not known yet: `None`
                # says to take it from the answer once it arrives.
                return self.__answerOnceBulkRead(
                    repetition,
                    rspVarBinds,
                    None,
                    M - 1,
                    R,
                    mgmtFun,
                    snmpEngine,
                    stateReference,
                    acFun,
                    acCtx,
                )

            rspVarBinds.extend(repetition)
            varBinds = rspVarBinds[-R:]
            M -= 1

        if rspVarBinds:
            self.sendVarBinds(snmpEngine, stateReference, 0, 0, rspVarBinds)
            self.releaseStateInformation(stateReference)
        else:
            raise pysnmp.smi.error.SmiError

    async def __answerOnceBulkRead(
        self,
        pending,
        rspVarBinds,
        varBinds,
        M,
        R,
        mgmtFun,
        snmpEngine,
        stateReference,
        acFun,
        acCtx,
    ):
        """Finish a GETBULK whose instrumentation had to be waited on.

        `pending` is the read already in flight and `rspVarBinds` what was
        gathered before it. `varBinds` is what the next repetition asks for, or
        `None` when that follows from what `pending` returns.
        """
        rspVarBinds = list(rspVarBinds)
        rspVarBinds.extend(await awaitInstrumentation(pending))

        if varBinds is None:
            varBinds = rspVarBinds[-R:]

        while M and R:
            rspVarBinds.extend(
                await awaitInstrumentation(
                    callInstrumentation(mgmtFun, varBinds, acFun=acFun, acCtx=acCtx)
                )
            )
            varBinds = rspVarBinds[-R:]
            M -= 1

        if rspVarBinds:
            self.sendVarBinds(snmpEngine, stateReference, 0, 0, rspVarBinds)
            self.releaseStateInformation(stateReference)
        else:
            raise pysnmp.smi.error.SmiError


class SetCommandResponder(CommandResponderBase):
    """Answers SET."""

    pduTypes = (rfc1905.SetRequestPDU.tagSet,)

    # rfc1905: 4.2.5
    def handleMgmtOperation(self, snmpEngine, stateReference, contextName, PDU, acInfo):
        """Write the bindings, which the instrumentation commits all or nothing."""
        (acFun, acCtx) = acInfo
        mgmtFun = self.snmpContext.getMibInstrum(contextName).writeVars
        # rfc1905: 4.2.5.1-13
        try:
            rspVarBinds = callInstrumentation(
                mgmtFun, v2c.apiPDU.getVarBinds(PDU), acFun=acFun, acCtx=acCtx
            )

            if isawaitable(rspVarBinds):
                return self.__answerOnceWritten(rspVarBinds, snmpEngine, stateReference)

            self.sendVarBinds(snmpEngine, stateReference, 0, 0, rspVarBinds)
            self.releaseStateInformation(stateReference)
        except (
            pysnmp.smi.error.NoSuchObjectError,
            pysnmp.smi.error.NoSuchInstanceError,
        ) as e:
            err = pysnmp.smi.error.NotWritableError()
            err.update(e)
            raise err from e

    async def __answerOnceWritten(self, awaitable, snmpEngine, stateReference):
        """Answer once instrumentation that had to be waited on has written.

        An object that turned out not to be there is reported as not writable
        here too: the requester asked to write it, and which of the two it is
        was decided by the same commit either way.
        """
        try:
            self.sendVarBinds(snmpEngine, stateReference, 0, 0, await awaitable)
            self.releaseStateInformation(stateReference)
        except (
            pysnmp.smi.error.NoSuchObjectError,
            pysnmp.smi.error.NoSuchInstanceError,
        ) as e:
            err = pysnmp.smi.error.NotWritableError()
            err.update(e)
            raise err from e
