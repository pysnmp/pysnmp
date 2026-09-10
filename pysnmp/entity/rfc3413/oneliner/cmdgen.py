#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# All code in this file belongs to obsolete, compatibility wrappers.
# Never use interfaces below for new applications!
#
"""Obsolete command generator wrappers. Use `pysnmp.hlapi` instead."""

from pyasn1.type import univ

from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.asyncio import sync
from pysnmp.hlapi.asyncio.cmdgen import bulkCmd, getCmd, nextCmd, setCmd
from pysnmp.hlapi.context import ContextData
from pysnmp.hlapi.lcd import CommandGeneratorLcdConfigurator
from pysnmp.hlapi.varbinds import CommandGeneratorVarBinds
from pysnmp.smi.rfc1902 import ObjectIdentity

__all__ = ["AsynCommandGenerator", "CommandGenerator", "MibVariable"]

MibVariable = ObjectIdentity


class AsynCommandGenerator:
    """Obsolete. Use `pysnmp.hlapi.asyncio`."""

    _null = univ.Null("")

    vbProcessor = CommandGeneratorVarBinds()
    lcd = CommandGeneratorLcdConfigurator()

    def __init__(self, snmpEngine=None):
        """Creates an engine if none is given, and owns it for its lifetime."""
        if snmpEngine is None:
            self.snmpEngine = SnmpEngine()
        else:
            self.snmpEngine = snmpEngine

        self.mibViewController = self.vbProcessor.getMibViewController(self.snmpEngine)

    def __del__(self):
        """Unconfigure this generator's targets from the engine."""
        self.lcd.unconfigure(self.snmpEngine)

    def cfgCmdGen(self, authData, transportTarget):
        """Obsolete. Configure credentials and a target on the engine."""
        return self.lcd.configure(self.snmpEngine, authData, transportTarget)

    def uncfgCmdGen(self, authData=None):
        """Obsolete. Remove what `cfgCmdGen` configured."""
        return self.lcd.unconfigure(self.snmpEngine, authData)

    # compatibility stub
    def makeReadVarBinds(self, varNames):
        """Obsolete. Pair each name with a null, as a read request wants."""
        return self.makeVarBinds([(x, self._null) for x in varNames])

    def makeVarBinds(self, varBinds):
        """Obsolete. Resolve bindings against the MIB."""
        return self.vbProcessor.makeVarBinds(self.snmpEngine, varBinds)

    def unmakeVarBinds(self, varBinds, lookupNames, lookupValues):
        """Obsolete. Turn resolved bindings back into names and values."""
        return self.vbProcessor.unmakeVarBinds(
            self.snmpEngine, varBinds, lookupNames or lookupValues
        )

    def getCmd(
        self,
        authData,
        transportTarget,
        varNames,
        cbInfo,
        lookupNames=False,
        lookupValues=False,
        contextEngineId=None,
        contextName=b"",
    ):
        """Obsolete. Use `pysnmp.hlapi.asyncio.get_cmd`."""

        def __cbFun(
            snmpEngine,
            sendRequestHandle,
            errorIndication,
            errorStatus,
            errorIndex,
            varBindTable,
            cbInfo,
        ):
            cbFun, cbCtx = cbInfo
            cbFun(
                sendRequestHandle,
                errorIndication,
                errorStatus,
                errorIndex,
                varBindTable,
                cbCtx,
            )

        # for backward compatibility
        if contextName == b"" and authData.contextName:
            contextName = authData.contextName

        return getCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(contextEngineId, contextName),
            *[(x, self._null) for x in varNames],
            cbFun=__cbFun,
            cbCtx=cbInfo,
            lookupMib=lookupNames or lookupValues,
        )

    asyncGetCmd = getCmd

    def setCmd(
        self,
        authData,
        transportTarget,
        varBinds,
        cbInfo,
        lookupNames=False,
        lookupValues=False,
        contextEngineId=None,
        contextName=b"",
    ):
        """Obsolete. Use `pysnmp.hlapi.asyncio.set_cmd`."""

        def __cbFun(
            snmpEngine,
            sendRequestHandle,
            errorIndication,
            errorStatus,
            errorIndex,
            varBindTable,
            cbInfo,
        ):
            cbFun, cbCtx = cbInfo
            cbFun(
                sendRequestHandle,
                errorIndication,
                errorStatus,
                errorIndex,
                varBindTable,
                cbCtx,
            )

        # for backward compatibility
        if contextName == b"" and authData.contextName:
            contextName = authData.contextName

        return setCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(contextEngineId, contextName),
            *varBinds,
            cbFun=__cbFun,
            cbCtx=cbInfo,
            lookupMib=lookupNames or lookupValues,
        )

    asyncSetCmd = setCmd

    def nextCmd(
        self,
        authData,
        transportTarget,
        varNames,
        cbInfo,
        lookupNames=False,
        lookupValues=False,
        contextEngineId=None,
        contextName=b"",
    ):
        """Obsolete. Use `pysnmp.hlapi.asyncio.next_cmd`."""

        def __cbFun(
            snmpEngine,
            sendRequestHandle,
            errorIndication,
            errorStatus,
            errorIndex,
            varBindTable,
            cbInfo,
        ):
            cbFun, cbCtx = cbInfo
            return cbFun(
                sendRequestHandle,
                errorIndication,
                errorStatus,
                errorIndex,
                varBindTable,
                cbCtx,
            )

        # for backward compatibility
        if contextName == b"" and authData.contextName:
            contextName = authData.contextName

        return nextCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(contextEngineId, contextName),
            *[(x, self._null) for x in varNames],
            cbFun=__cbFun,
            cbCtx=cbInfo,
            lookupMib=lookupNames or lookupValues,
        )

    asyncNextCmd = nextCmd

    def bulkCmd(
        self,
        authData,
        transportTarget,
        nonRepeaters,
        maxRepetitions,
        varNames,
        cbInfo,
        lookupNames=False,
        lookupValues=False,
        contextEngineId=None,
        contextName=b"",
    ):
        """Obsolete. Use `pysnmp.hlapi.asyncio.bulk_cmd`."""

        def __cbFun(
            snmpEngine,
            sendRequestHandle,
            errorIndication,
            errorStatus,
            errorIndex,
            varBindTable,
            cbInfo,
        ):
            cbFun, cbCtx = cbInfo
            return cbFun(
                sendRequestHandle,
                errorIndication,
                errorStatus,
                errorIndex,
                varBindTable,
                cbCtx,
            )

        # for backward compatibility
        if contextName == b"" and authData.contextName:
            contextName = authData.contextName

        return bulkCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(contextEngineId, contextName),
            nonRepeaters,
            maxRepetitions,
            *[(x, self._null) for x in varNames],
            cbFun=__cbFun,
            cbCtx=cbInfo,
            lookupMib=lookupNames or lookupValues,
        )

    asyncBulkCmd = bulkCmd


class CommandGenerator:
    """Obsolete. Use `pysnmp.hlapi`."""

    _null = univ.Null("")

    def __init__(self, snmpEngine=None, asynCmdGen=None):
        """`asynCmdGen` is accepted for compatibility and ignored."""
        self.snmpEngine = snmpEngine or SnmpEngine()

    def getCmd(self, authData, transportTarget, *varNames, **kwargs):
        """Obsolete. Use `pysnmp.hlapi.asyncio.sync.get_cmd`."""
        if "lookupNames" not in kwargs:
            kwargs["lookupNames"] = False
        if "lookupValues" not in kwargs:
            kwargs["lookupValues"] = False
        errorIndication, errorStatus, errorIndex, varBinds = None, 0, 0, []
        for errorIndication, errorStatus, errorIndex, varBinds in sync.getCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(kwargs.get("contextEngineId"), kwargs.get("contextName", b"")),
            *[(x, self._null) for x in varNames],
            **kwargs,
        ):
            break
        return errorIndication, errorStatus, errorIndex, varBinds

    def setCmd(self, authData, transportTarget, *varBinds, **kwargs):
        """Obsolete. Use `pysnmp.hlapi.asyncio.sync.set_cmd`."""
        if "lookupNames" not in kwargs:
            kwargs["lookupNames"] = False
        if "lookupValues" not in kwargs:
            kwargs["lookupValues"] = False
        errorIndication, errorStatus, errorIndex, rspVarBinds = None, 0, 0, []
        for errorIndication, errorStatus, errorIndex, rspVarBinds in sync.setCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(kwargs.get("contextEngineId"), kwargs.get("contextName", b"")),
            *varBinds,
            **kwargs,
        ):
            break

        return errorIndication, errorStatus, errorIndex, rspVarBinds

    def nextCmd(self, authData, transportTarget, *varNames, **kwargs):
        """Obsolete. Use `pysnmp.hlapi.asyncio.sync.next_cmd`."""
        if "lookupNames" not in kwargs:
            kwargs["lookupNames"] = False
        if "lookupValues" not in kwargs:
            kwargs["lookupValues"] = False
        if "lexicographicMode" not in kwargs:
            kwargs["lexicographicMode"] = False
        errorIndication, errorStatus, errorIndex = None, 0, 0
        varBindTable = []
        for errorIndication, errorStatus, errorIndex, varBinds in sync.nextCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(kwargs.get("contextEngineId"), kwargs.get("contextName", b"")),
            *[(x, self._null) for x in varNames],
            **kwargs,
        ):
            if errorIndication or errorStatus:
                return errorIndication, errorStatus, errorIndex, varBinds

            varBindTable.append(varBinds)

        return errorIndication, errorStatus, errorIndex, varBindTable

    def bulkCmd(
        self,
        authData,
        transportTarget,
        nonRepeaters,
        maxRepetitions,
        *varNames,
        **kwargs,
    ):
        """Obsolete. Use `pysnmp.hlapi.asyncio.sync.bulk_cmd`."""
        if "lookupNames" not in kwargs:
            kwargs["lookupNames"] = False
        if "lookupValues" not in kwargs:
            kwargs["lookupValues"] = False
        if "lexicographicMode" not in kwargs:
            kwargs["lexicographicMode"] = False
        errorIndication, errorStatus, errorIndex = None, 0, 0
        varBindTable = []
        for errorIndication, errorStatus, errorIndex, varBinds in sync.bulkCmd(
            self.snmpEngine,
            authData,
            transportTarget,
            ContextData(kwargs.get("contextEngineId"), kwargs.get("contextName", b"")),
            nonRepeaters,
            maxRepetitions,
            *[(x, self._null) for x in varNames],
            **kwargs,
        ):
            if errorIndication or errorStatus:
                return errorIndication, errorStatus, errorIndex, varBinds

            varBindTable.append(varBinds)

        return errorIndication, errorStatus, errorIndex, varBindTable
