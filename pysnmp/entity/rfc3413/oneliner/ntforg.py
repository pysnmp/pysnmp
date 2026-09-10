#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# All code in this file belongs to obsolete, compatibility wrappers.
# Never use interfaces below for new applications!
#
"""Obsolete notification originator wrappers. Use `pysnmp.hlapi` instead."""

from pysnmp.entity import config
from pysnmp.entity.engine import SnmpEngine
from pysnmp.entity.rfc3413 import context
from pysnmp.hlapi.asyncio import sync
from pysnmp.hlapi.asyncio.ntforg import sendNotification
from pysnmp.hlapi.context import ContextData
from pysnmp.hlapi.lcd import NotificationOriginatorLcdConfigurator
from pysnmp.hlapi.varbinds import NotificationOriginatorVarBinds
from pysnmp.smi.rfc1902 import NotificationType, ObjectIdentity, ObjectType

__all__ = ["AsynNotificationOriginator", "MibVariable", "NotificationOriginator"]

MibVariable = ObjectIdentity


class ErrorIndicationReturn:
    def __init__(self, *vars):
        """Holds the tuple a legacy caller unpacks, error indication first."""
        self.__vars = vars

    def __getitem__(self, i):
        """One element of the result tuple."""
        return self.__vars[i]

    def __bool__(self):
        """Truthy where there is an error indication, so `if result:` means failure."""
        return bool(self.__vars[0])

    def __str__(self):
        """The error indication alone."""
        return str(self.__vars[0])


class AsynNotificationOriginator:
    """Obsolete. Use `pysnmp.hlapi.asyncio`."""

    vbProcessor = NotificationOriginatorVarBinds()
    lcd = NotificationOriginatorLcdConfigurator()

    def __init__(self, snmpEngine=None, snmpContext=None):
        """Creates an engine and a default context if neither is given.

        The default context it adds is never removed, which is one of the reasons this
        class is obsolete.
        """
        if snmpEngine is None:
            self.snmpEngine = snmpEngine = SnmpEngine()
        else:
            self.snmpEngine = snmpEngine

        if snmpContext is None:
            self.snmpContext = context.SnmpContext(self.snmpEngine)
            config.addContext(self.snmpEngine, "")  # this is leaky
        else:
            self.snmpContext = snmpContext

        self.mibViewController = self.vbProcessor.getMibViewController(self.snmpEngine)

    def __del__(self):
        """Unconfigure this originator's targets from the engine."""
        self.uncfgNtfOrg()

    def cfgNtfOrg(self, authData, transportTarget, notifyType):
        """Obsolete. Configure credentials, a target and a notify type on the engine."""
        return self.lcd.configure(
            self.snmpEngine, authData, transportTarget, notifyType
        )

    def uncfgNtfOrg(self, authData=None):
        """Obsolete. Remove what `cfgNtfOrg` configured."""
        return self.lcd.unconfigure(self.snmpEngine, authData)

    def makeVarBinds(self, varBinds):
        """Obsolete. Resolve bindings against the MIB."""
        return self.vbProcessor.makeVarBinds(self.snmpEngine, varBinds)

    def unmakeVarBinds(self, varBinds, lookupNames, lookupValues):
        """Obsolete. Turn resolved bindings back into names and values."""
        return self.vbProcessor.unmakeVarBinds(
            self.snmpEngine, varBinds, lookupNames or lookupValues
        )

    def sendNotification(
        self,
        authData,
        transportTarget,
        notifyType,
        notificationType,
        varBinds=(),  # legacy, use NotificationType instead
        cbInfo=(None, None),
        lookupNames=False,
        lookupValues=False,
        contextEngineId=None,  # XXX ordering incompatibility
        contextName=b"",
    ):
        """Obsolete. Use `pysnmp.hlapi.asyncio.send_notification`."""

        def __cbFun(
            snmpEngine,
            sendRequestHandle,
            errorIndication,
            errorStatus,
            errorIndex,
            varBinds,
            cbCtx,
        ):
            cbFun, cbCtx = cbCtx
            try:
                # we need to pass response PDU information to user for INFORMs
                return cbFun and cbFun(
                    sendRequestHandle,
                    errorIndication,
                    errorStatus,
                    errorIndex,
                    varBinds,
                    cbCtx,
                )
            except TypeError:
                # a backward compatible way of calling user function
                return cbFun(sendRequestHandle, errorIndication, cbCtx)

        # for backward compatibility
        if contextName == b"" and authData.contextName:
            contextName = authData.contextName

        if not isinstance(
            notificationType, (ObjectIdentity, ObjectType, NotificationType)
        ):
            if isinstance(notificationType[0], tuple):
                # legacy
                notificationType = ObjectIdentity(
                    notificationType[0][0],
                    notificationType[0][1],
                    *notificationType[1:],
                )
            else:
                notificationType = ObjectIdentity(notificationType)

        if not isinstance(notificationType, NotificationType):
            notificationType = NotificationType(notificationType)

        return sendNotification(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(
                contextEngineId or self.snmpContext.contextEngineId, contextName
            ),
            notifyType,
            notificationType.addVarBinds(*varBinds),
            __cbFun,
            cbInfo,
            lookupNames or lookupValues,
        )

    asyncSendNotification = sendNotification


class NotificationOriginator:
    """Obsolete. Use `pysnmp.hlapi`."""

    vbProcessor = NotificationOriginatorVarBinds()

    def __init__(self, snmpEngine=None, snmpContext=None, asynNtfOrg=None):
        """`asynNtfOrg` is accepted for compatibility and ignored."""
        self.snmpEngine = snmpEngine or SnmpEngine()
        self.mibViewController = self.vbProcessor.getMibViewController(self.snmpEngine)

    # the varBinds parameter is legacy, use NotificationType instead

    def sendNotification(
        self,
        authData,
        transportTarget,
        notifyType,
        notificationType,
        *varBinds,
        **kwargs,
    ):
        """Obsolete. Use `pysnmp.hlapi.asyncio.sync.send_notification`."""
        if "lookupNames" not in kwargs:
            kwargs["lookupNames"] = False
        if "lookupValues" not in kwargs:
            kwargs["lookupValues"] = False
        if not isinstance(
            notificationType, (ObjectIdentity, ObjectType, NotificationType)
        ):
            if isinstance(notificationType[0], tuple):
                # legacy
                notificationType = ObjectIdentity(
                    notificationType[0][0],
                    notificationType[0][1],
                    *notificationType[1:],
                )
            else:
                notificationType = ObjectIdentity(notificationType)

        if not isinstance(notificationType, NotificationType):
            notificationType = NotificationType(notificationType)

        for (
            errorIndication,
            errorStatus,
            errorIndex,
            rspVarBinds,
        ) in sync.sendNotification(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(kwargs.get("contextEngineId"), kwargs.get("contextName", b"")),
            notifyType,
            notificationType.addVarBinds(*varBinds),
            **kwargs,
        ):
            if notifyType == "inform":
                return errorIndication, errorStatus, errorIndex, rspVarBinds
            else:
                break
