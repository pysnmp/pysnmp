#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

from pyasn1.compat.octets import null

from pysnmp import debug, nextid
from pysnmp.entity.rfc3413 import config
from pysnmp.proto import errind, error, rfc3411
from pysnmp.proto.api import v2c
from pysnmp.proto.proxy import rfc2576
from pysnmp.smi import rfc1902, view

getNextHandle = nextid.Integer(0x7FFFFFFF)

# Bit weights for mask processing (MSB first within each octet)
_POWER_OF_TWO = [2**exp for exp in range(7, -1, -1)]


def _matchFilter(filterEntries, oid):
    """Apply RFC 3413 §6 notification filter matching to *oid*.

    *filterEntries* is a list of ``(subtree, mask, filterType)`` tuples
    as returned by :func:`getNotifyFilter`.

    Returns ``True`` when *oid* is **included** (the notification should
    be sent) or ``False`` when *oid* is **excluded**.

    The algorithm mirrors the VACM view-tree family matching in
    RFC 3415 §3.2.5:

    * Each filter entry's *mask* is expanded with 1-bits when shorter than
      the subtree (zero-length mask ⇒ all-1's ⇒ exact match).
    * Sub-identifiers where the mask bit is 0 are wildcards (ignored).
    * Entries are sorted by ``(len(subtree), subtree)`` so the **longest
      match wins**; ties are broken lexicographically (largest wins).
    * If no entry matches, the default is **included**.
    """
    if not filterEntries:
        return True

    prepared = []
    for subtree, mask, filterType in filterEntries:
        maskOctets = mask.asNumbers()
        maskLength = min(len(maskOctets) * 8, len(subtree))

        ignoredSubOids = [
            i * 8 + j
            for i, octet in enumerate(maskOctets)
            for j, bit in enumerate(_POWER_OF_TWO)
            if not (bit & octet) and i * 8 + j < maskLength
        ]

        if ignoredSubOids:
            pattern = list(subtree)
            for idx in ignoredSubOids:
                if idx < len(pattern):
                    pattern[idx] = 0
            normalizedSubtree = subtree.clone(pattern)
        else:
            normalizedSubtree = subtree

        # filterType: included(1) → True, excluded(2) → False
        included = int(filterType) == 1
        prepared.append((normalizedSubtree, ignoredSubOids, included))

    # Sort by (len(subtree), subtree) — longest match wins, ties broken
    # lexicographically (largest subtree wins, per RFC 3413 §6).
    prepared.sort(key=lambda e: (len(e[0]), e[0]))

    result = True  # default: included
    for subtree, ignoredSubOids, included in prepared:
        if ignoredSubOids:
            subOids = list(oid)
            for idx in ignoredSubOids:
                if idx < len(subOids):
                    subOids[idx] = 0
            normalizedOid = subtree.clone(subOids)
        else:
            normalizedOid = oid

        if subtree.isPrefixOf(normalizedOid):
            result = included

    return result


class NotificationOriginator:
    acmID = 3  # default MIB access control method to use

    def __init__(self, **options):
        self.__pendingReqs = {}
        self.__pendingNotifications = {}
        self.snmpContext = options.pop('snmpContext', None)  # this is deprecated
        self.__options = options

    def processResponsePdu(
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
        statusInformation,
        sendPduHandle,
        cbInfo,
    ):
        sendRequestHandle, cbFun, cbCtx = cbInfo

        # 3.3.6d
        if sendPduHandle not in self.__pendingReqs:
            raise error.ProtocolError('Missing sendPduHandle %s' % sendPduHandle)

        (
            origTransportDomain,
            origTransportAddress,
            origMessageProcessingModel,
            origSecurityModel,
            origSecurityName,
            origSecurityLevel,
            origContextEngineId,
            origContextName,
            origPdu,
            origTimeout,
            origRetryCount,
            origRetries,
            origDiscoveryRetries,
        ) = self.__pendingReqs.pop(sendPduHandle)

        snmpEngine.transportDispatcher.jobFinished(id(self))

        if statusInformation:
            debug.logger & debug.flagApp and debug.logger(
                'processResponsePdu: sendRequestHandle {}, sendPduHandle {} statusInformation {}'.format(
                    sendRequestHandle, sendPduHandle, statusInformation
                )
            )

            errorIndication = statusInformation['errorIndication']

            if errorIndication in (errind.notInTimeWindow, errind.unknownEngineID):
                origDiscoveryRetries += 1
                origRetries = 0
            else:
                origDiscoveryRetries = 0
                origRetries += 1

            if origRetries > origRetryCount or origDiscoveryRetries > self.__options.get(
                'discoveryRetries', 4
            ):
                debug.logger & debug.flagApp and debug.logger(
                    'processResponsePdu: sendRequestHandle %s, sendPduHandle %s retry count %d exceeded'
                    % (sendRequestHandle, sendPduHandle, origRetries)
                )
                cbFun(snmpEngine, sendRequestHandle, errorIndication, None, cbCtx)
                return

            # Convert timeout in seconds into timeout in timer ticks
            timeoutInTicks = (
                float(origTimeout) / 100 / snmpEngine.transportDispatcher.getTimerResolution()
            )

            # User-side API assumes SMIv2
            if messageProcessingModel == 0:
                reqPDU = rfc2576.v2ToV1(origPdu)
                pduVersion = 0
            else:
                reqPDU = origPdu
                pduVersion = 1

            # 3.3.6a
            try:
                sendPduHandle = snmpEngine.msgAndPduDsp.sendPdu(
                    snmpEngine,
                    origTransportDomain,
                    origTransportAddress,
                    origMessageProcessingModel,
                    origSecurityModel,
                    origSecurityName,
                    origSecurityLevel,
                    origContextEngineId,
                    origContextName,
                    pduVersion,
                    reqPDU,
                    True,
                    timeoutInTicks,
                    self.processResponsePdu,
                    (sendRequestHandle, cbFun, cbCtx),
                )
            except error.StatusInformation as statusInformation:
                debug.logger & debug.flagApp and debug.logger(
                    'processResponsePdu: sendRequestHandle {}: sendPdu() failed with {!r} '.format(
                        sendRequestHandle, statusInformation
                    )
                )
                cbFun(
                    snmpEngine,
                    sendRequestHandle,
                    statusInformation['errorIndication'],
                    None,
                    cbCtx,
                )
                return

            snmpEngine.transportDispatcher.jobStarted(id(self))

            debug.logger & debug.flagApp and debug.logger(
                'processResponsePdu: sendRequestHandle %s, sendPduHandle %s, timeout %d, retry %d of %d'
                % (sendRequestHandle, sendPduHandle, origTimeout, origRetries, origRetryCount)
            )

            # 3.3.6b
            self.__pendingReqs[sendPduHandle] = (
                origTransportDomain,
                origTransportAddress,
                origMessageProcessingModel,
                origSecurityModel,
                origSecurityName,
                origSecurityLevel,
                origContextEngineId,
                origContextName,
                origPdu,
                origTimeout,
                origRetryCount,
                origRetries,
                origDiscoveryRetries,
            )
            return

        # 3.3.6c
        # User-side API assumes SMIv2
        if messageProcessingModel == 0:
            PDU = rfc2576.v1ToV2(PDU, origPdu)

        cbFun(snmpEngine, sendRequestHandle, None, PDU, cbCtx)

    def sendPdu(
        self, snmpEngine, targetName, contextEngineId, contextName, pdu, cbFun=None, cbCtx=None
    ):
        (transportDomain, transportAddress, timeout, retryCount, params) = config.getTargetAddr(
            snmpEngine, targetName
        )

        (messageProcessingModel, securityModel, securityName, securityLevel) = (
            config.getTargetParams(snmpEngine, params)
        )

        # User-side API assumes SMIv2
        if messageProcessingModel == 0:
            reqPDU = rfc2576.v2ToV1(pdu)
            pduVersion = 0
        else:
            reqPDU = pdu
            pduVersion = 1

        # 3.3.5
        if reqPDU.tagSet in rfc3411.confirmedClassPDUs:
            # Convert timeout in seconds into timeout in timer ticks
            timeoutInTicks = (
                float(timeout) / 100 / snmpEngine.transportDispatcher.getTimerResolution()
            )

            sendRequestHandle = getNextHandle()

            # 3.3.6a
            sendPduHandle = snmpEngine.msgAndPduDsp.sendPdu(
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
                reqPDU,
                True,
                timeoutInTicks,
                self.processResponsePdu,
                (sendRequestHandle, cbFun, cbCtx),
            )

            debug.logger & debug.flagApp and debug.logger(
                'sendPdu: sendPduHandle %s, timeout %d' % (sendPduHandle, timeout)
            )

            # 3.3.6b
            self.__pendingReqs[sendPduHandle] = (
                transportDomain,
                transportAddress,
                messageProcessingModel,
                securityModel,
                securityName,
                securityLevel,
                contextEngineId,
                contextName,
                pdu,
                timeout,
                retryCount,
                0,
                0,
            )
            snmpEngine.transportDispatcher.jobStarted(id(self))
        else:
            snmpEngine.msgAndPduDsp.sendPdu(
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
                reqPDU,
                False,
            )

            sendRequestHandle = None

            debug.logger & debug.flagApp and debug.logger('sendPdu: message sent')

        return sendRequestHandle

    def processResponseVarBinds(self, snmpEngine, sendRequestHandle, errorIndication, pdu, cbCtx):
        notificationHandle, cbFun, cbCtx = cbCtx

        self.__pendingNotifications[notificationHandle].remove(sendRequestHandle)

        debug.logger & debug.flagApp and debug.logger(
            'processResponseVarBinds: notificationHandle {}, sendRequestHandle {}, errorIndication {}, pending requests {}'.format(
                notificationHandle,
                sendRequestHandle,
                errorIndication,
                self.__pendingNotifications[notificationHandle],
            )
        )

        if not self.__pendingNotifications[notificationHandle]:
            debug.logger & debug.flagApp and debug.logger(
                'processResponseVarBinds: notificationHandle {}, sendRequestHandle {} -- completed'.format(
                    notificationHandle, sendRequestHandle
                )
            )
            del self.__pendingNotifications[notificationHandle]
            cbFun(
                snmpEngine,
                sendRequestHandle,
                errorIndication,
                pdu and v2c.apiPDU.getErrorStatus(pdu) or 0,
                pdu and v2c.apiPDU.getErrorIndex(pdu, muteErrors=True) or 0,
                pdu and v2c.apiPDU.getVarBinds(pdu) or (),
                cbCtx,
            )

    #
    # Higher-level API to Notification Originator. Supports multiple
    # targets, automatic var-binding formation and is fully LCD-driven.
    #
    def sendVarBinds(
        self,
        snmpEngine,
        notificationTarget,
        contextEngineId,
        contextName,
        varBinds=(),
        cbFun=None,
        cbCtx=None,
    ):
        debug.logger & debug.flagApp and debug.logger(
            'sendVarBinds: notificationTarget {}, contextEngineId {}, contextName "{}", varBinds {}'.format(
                notificationTarget, contextEngineId or '<default>', contextName, varBinds
            )
        )

        if contextName:
            (__SnmpAdminString,) = (
                snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                    'SNMP-FRAMEWORK-MIB', 'SnmpAdminString'
                )
            )
            contextName = __SnmpAdminString(contextName)

        # 3.3
        (notifyTag, notifyType) = config.getNotificationInfo(snmpEngine, notificationTarget)

        notificationHandle = getNextHandle()

        debug.logger & debug.flagApp and debug.logger(
            'sendVarBinds: notificationHandle {}, notifyTag {}, notifyType {}'.format(
                notificationHandle, notifyTag, notifyType
            )
        )

        varBinds = [(v2c.ObjectIdentifier(x), y) for x, y in varBinds]

        # 3.3.2 & 3.3.3
        snmpTrapOID, sysUpTime = (
            snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                '__SNMPv2-MIB', 'snmpTrapOID', 'sysUpTime'
            )
        )

        for idx in range(len(varBinds)):
            if idx and varBinds[idx][0] == sysUpTime.getName():
                if varBinds[0][0] == sysUpTime.getName():
                    varBinds[0] = varBinds[idx]
                else:
                    varBinds.insert(0, varBinds[idx])
                    del varBinds[idx]

            if varBinds[0][0] != sysUpTime.getName():
                varBinds.insert(
                    0, (v2c.ObjectIdentifier(sysUpTime.getName()), sysUpTime.getSyntax().clone())
                )

        if len(varBinds) < 2 or varBinds[1][0] != snmpTrapOID.getName():
            varBinds.insert(
                1, (v2c.ObjectIdentifier(snmpTrapOID.getName()), snmpTrapOID.getSyntax())
            )

        sendRequestHandle = -1

        debug.logger & debug.flagApp and debug.logger(f'sendVarBinds: final varBinds {varBinds}')

        for targetAddrName in config.getTargetNames(snmpEngine, notifyTag):
            (transportDomain, transportAddress, timeout, retryCount, params) = (
                config.getTargetAddr(snmpEngine, targetAddrName)
            )
            (messageProcessingModel, securityModel, securityName, securityLevel) = (
                config.getTargetParams(snmpEngine, params)
            )

            # 3.3.1 — RFC 3413 §6 notification filtering
            filterProfileName = config.getNotifyFilterProfile(snmpEngine, params)

            targetVarBinds = varBinds
            if filterProfileName is not None:
                filterEntries = config.getNotifyFilter(snmpEngine, filterProfileName)

                debug.logger & debug.flagApp and debug.logger(
                    'sendVarBinds: filterProfileName {!r}, filterEntries {}'.format(
                        filterProfileName, filterEntries
                    )
                )

                if filterEntries:
                    # Per RFC 3413 §6: the notification may be sent only if
                    # the snmpTrapOID value (the notification name) is
                    # specifically *included* by the filter entries, AND none
                    # of the object-instance varBinds are specifically
                    # *excluded*.
                    #
                    # sysUpTime and snmpTrapOID are protocol-mandated
                    # varBinds and are never subject to filtering.

                    # Check the notification name (snmpTrapOID value)
                    trapOidVal = varBinds[1][1]  # value of snmpTrapOID varbind
                    if not _matchFilter(filterEntries, trapOidVal):
                        debug.logger & debug.flagApp and debug.logger(
                            'sendVarBinds: notification name {} excluded by filter for target {}, skipping'.format(
                                trapOidVal, targetAddrName
                            )
                        )
                        continue

                    # Check each object-instance varBind
                    filteredVarBinds = []
                    for varName, varVal in varBinds:
                        if varName in (sysUpTime.name, snmpTrapOID.name):
                            filteredVarBinds.append((varName, varVal))
                            continue
                        if _matchFilter(filterEntries, varName):
                            filteredVarBinds.append((varName, varVal))
                        else:
                            debug.logger & debug.flagApp and debug.logger(
                                'sendVarBinds: varBind {} excluded by filter for target {}'.format(
                                    varName, targetAddrName
                                )
                            )

                    # If only the protocol varBinds remain, nothing to send
                    if len(filteredVarBinds) <= 2:
                        debug.logger & debug.flagApp and debug.logger(
                            'sendVarBinds: all object varBinds excluded by filter for target {}, skipping'.format(
                                targetAddrName
                            )
                        )
                        continue

                    targetVarBinds = filteredVarBinds

            debug.logger & debug.flagApp and debug.logger(
                'sendVarBinds: notificationHandle {}, notifyTag {} yields: transportDomain {}, transportAddress {!r}, securityModel {}, securityName {}, securityLevel {}'.format(
                    notificationHandle,
                    notifyTag,
                    transportDomain,
                    transportAddress,
                    securityModel,
                    securityName,
                    securityLevel,
                )
            )

            vacmDenied = False
            for varName, varVal in targetVarBinds:
                if varName in (sysUpTime.name, snmpTrapOID.name):
                    continue
                try:
                    snmpEngine.accessControlModel[self.acmID].isAccessAllowed(
                        snmpEngine,
                        securityModel,
                        securityName,
                        securityLevel,
                        'notify',
                        contextName,
                        varName,
                    )

                    debug.logger & debug.flagApp and debug.logger(
                        f'sendVarBinds: ACL succeeded for OID {varName} securityName {securityName}'
                    )

                except error.StatusInformation:
                    debug.logger & debug.flagApp and debug.logger(
                        'sendVarBinds: ACL denied access for OID {} securityName {}, '
                        'skipping notification for target {}'.format(
                            varName, securityName, targetAddrName
                        )
                    )
                    vacmDenied = True
                    break

            if vacmDenied:
                continue

            # 3.3.4
            if notifyType == 1:
                pdu = v2c.SNMPv2TrapPDU()
            elif notifyType == 2:
                pdu = v2c.InformRequestPDU()
            else:
                raise error.ProtocolError('Unknown notify-type %r', notifyType)

            v2c.apiPDU.setDefaults(pdu)
            v2c.apiPDU.setVarBinds(pdu, targetVarBinds)

            # 3.3.5
            try:
                sendRequestHandle = self.sendPdu(
                    snmpEngine,
                    targetAddrName,
                    contextEngineId,
                    contextName,
                    pdu,
                    self.processResponseVarBinds,
                    (notificationHandle, cbFun, cbCtx),
                )

            except error.StatusInformation as statusInformation:
                debug.logger & debug.flagApp and debug.logger(
                    'sendVarBinds: sendRequestHandle {}: sendPdu() failed with {!r}'.format(
                        sendRequestHandle, statusInformation
                    )
                )
                if (
                    notificationHandle not in self.__pendingNotifications
                    or not self.__pendingNotifications[notificationHandle]
                ):
                    if notificationHandle in self.__pendingNotifications:
                        del self.__pendingNotifications[notificationHandle]
                    if cbFun:
                        cbFun(
                            snmpEngine,
                            notificationHandle,
                            statusInformation['errorIndication'],
                            0,
                            0,
                            (),
                            cbCtx,
                        )
                return notificationHandle

            debug.logger & debug.flagApp and debug.logger(
                'sendVarBinds: notificationHandle %s, sendRequestHandle %s, timeout %d'
                % (notificationHandle, sendRequestHandle, timeout)
            )

            if notifyType == 2:
                if notificationHandle not in self.__pendingNotifications:
                    self.__pendingNotifications[notificationHandle] = set()
                self.__pendingNotifications[notificationHandle].add(sendRequestHandle)

        debug.logger & debug.flagApp and debug.logger(
            'sendVarBinds: notificationHandle {}, sendRequestHandle {}, notification(s) sent'.format(
                notificationHandle, sendRequestHandle
            )
        )

        return notificationHandle


#
# Obsolete, compatibility interfaces.
#


def _sendNotificationCbFun(
    snmpEngine, sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, cbCtx
):
    cbFun, cbCtx = cbCtx

    try:
        # we need to pass response PDU information to user for INFORMs
        cbFun(sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, cbCtx)
    except TypeError:
        # a backward compatible way of calling user function
        cbFun(sendRequestHandle, errorIndication, cbCtx)


def _sendNotification(
    self,
    snmpEngine,
    notificationTarget,
    notificationName,
    additionalVarBinds=(),
    cbFun=None,
    cbCtx=None,
    contextName=null,
    instanceIndex=None,
):
    if self.snmpContext is None:
        raise error.ProtocolError('SNMP context not specified')

    #
    # Here we first expand trap OID into associated OBJECTS
    # and then look them up at context-specific MIB
    #

    mibViewController = snmpEngine.getUserContext('mibViewController')
    if not mibViewController:
        mibViewController = view.MibViewController(snmpEngine.getMibBuilder())
        snmpEngine.setUserContext(mibViewController=mibViewController)

    # Support the following syntax:
    #   '1.2.3.4'
    #   (1,2,3,4)
    #   ('MIB', 'symbol')
    if (
        isinstance(notificationName, (tuple, list))
        and notificationName
        and isinstance(notificationName[0], str)
    ):
        notificationName = rfc1902.ObjectIdentity(*notificationName)
    else:
        notificationName = rfc1902.ObjectIdentity(notificationName)

    varBinds = rfc1902.NotificationType(notificationName, instanceIndex=instanceIndex)
    varBinds.resolveWithMib(mibViewController)

    mibInstrumController = self.snmpContext.getMibInstrum(contextName)

    varBinds = varBinds[:1] + mibInstrumController.readVars(varBinds[1:])

    return self.sendVarBinds(
        snmpEngine,
        notificationTarget,
        self.snmpContext.contextEngineId,
        contextName,
        varBinds + list(additionalVarBinds),
        _sendNotificationCbFun,
        (cbFun, cbCtx),
    )


# install compatibility wrapper
NotificationOriginator.sendNotification = _sendNotification

# XXX
# move/group/implement config setting/retrieval at a stand-alone module
