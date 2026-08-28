import asyncio

from pyasn1.type.univ import Null

from pysnmp.hlapi.asyncio import cmdgen
from pysnmp.hlapi.varbinds import CommandGeneratorVarBinds
from pysnmp.proto import errind
from pysnmp.proto.rfc1905 import endOfMibView

__all__ = ['getCmd', 'nextCmd', 'setCmd', 'bulkCmd']


def _loop():
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.new_event_loop()
    raise RuntimeError(
        'The synchronous HLAPI cannot run while an asyncio event loop is running; '
        'use pysnmp.hlapi.asyncio instead'
    )


def _close(loop, snmpEngine):
    if snmpEngine.transportDispatcher is not None:
        snmpEngine.transportDispatcher.closeDispatcher()
        loop.run_until_complete(asyncio.sleep(0))
    loop.close()


def _single(command, snmpEngine, authData, transportTarget, contextData, varBinds, options):
    loop = _loop()
    try:
        asyncio.set_event_loop(loop)
        while True:
            if varBinds:
                result = loop.run_until_complete(
                    command(
                        snmpEngine, authData, transportTarget, contextData, *varBinds, **options
                    )
                )
            else:
                result = None, None, None, []
            varBinds = yield result
            if not varBinds:
                return
    finally:
        _close(loop, snmpEngine)
        asyncio.set_event_loop(None)


def getCmd(snmpEngine, authData, transportTarget, contextData, *varBinds, **options):
    return _single(
        cmdgen.getCmd, snmpEngine, authData, transportTarget, contextData, varBinds, options
    )


def setCmd(snmpEngine, authData, transportTarget, contextData, *varBinds, **options):
    return _single(
        cmdgen.setCmd, snmpEngine, authData, transportTarget, contextData, varBinds, options
    )


def nextCmd(snmpEngine, authData, transportTarget, contextData, *varBinds, **options):
    loop = _loop()
    lexicographicMode = options.pop('lexicographicMode', True)
    ignoreNonIncreasingOid = options.pop('ignoreNonIncreasingOid', False)
    maxRows = options.pop('maxRows', 0)
    maxCalls = options.pop('maxCalls', 0)
    vbProcessor = CommandGeneratorVarBinds()
    initialVars = [x[0] for x in vbProcessor.makeVarBinds(snmpEngine, varBinds)]
    totalRows = totalCalls = 0

    try:
        asyncio.set_event_loop(loop)
        while varBinds:
            previousVarBinds = varBinds
            errorIndication, errorStatus, errorIndex, varBindTable = loop.run_until_complete(
                cmdgen.nextCmd(
                    snmpEngine,
                    authData,
                    transportTarget,
                    contextData,
                    *[(x[0], Null('')) for x in varBinds],
                    **options,
                )
            )
            if ignoreNonIncreasingOid and isinstance(errorIndication, errind.OidNotIncreasing):
                errorIndication = None
            if errorIndication or errorStatus:
                yield errorIndication, errorStatus, errorIndex, varBinds
                return

            varBinds = varBindTable[0] if varBindTable else []
            stopFlag = True
            for column, (name, value) in enumerate(varBinds):
                if isinstance(value, Null) or (
                    not lexicographicMode and not initialVars[column].isPrefixOf(name)
                ):
                    varBinds[column] = previousVarBinds[column][0], endOfMibView
                if varBinds[column][1] is not endOfMibView:
                    stopFlag = False
            if stopFlag:
                return

            totalRows += 1
            totalCalls += 1
            nextVarBinds = yield errorIndication, errorStatus, errorIndex, varBinds
            if nextVarBinds:
                varBinds = nextVarBinds
                initialVars = [x[0] for x in vbProcessor.makeVarBinds(snmpEngine, varBinds)]
            if (maxRows and totalRows >= maxRows) or (maxCalls and totalCalls >= maxCalls):
                return
    finally:
        _close(loop, snmpEngine)
        asyncio.set_event_loop(None)


def bulkCmd(
    snmpEngine,
    authData,
    transportTarget,
    contextData,
    nonRepeaters,
    maxRepetitions,
    *varBinds,
    **options,
):
    loop = _loop()
    lexicographicMode = options.pop('lexicographicMode', True)
    ignoreNonIncreasingOid = options.pop('ignoreNonIncreasingOid', False)
    maxRows = options.pop('maxRows', 0)
    maxCalls = options.pop('maxCalls', 0)
    vbProcessor = CommandGeneratorVarBinds()
    initialVars = [x[0] for x in vbProcessor.makeVarBinds(snmpEngine, varBinds)]
    nullVarBinds = [False] * len(initialVars)
    totalRows = totalCalls = 0

    try:
        asyncio.set_event_loop(loop)
        while varBinds:
            repetitions = min(maxRepetitions, maxRows - totalRows) if maxRows else maxRepetitions
            errorIndication, errorStatus, errorIndex, varBindTable = loop.run_until_complete(
                cmdgen.bulkCmd(
                    snmpEngine,
                    authData,
                    transportTarget,
                    contextData,
                    nonRepeaters,
                    repetitions,
                    *[(x[0], Null('')) for x in varBinds],
                    **options,
                )
            )
            if ignoreNonIncreasingOid and isinstance(errorIndication, errind.OidNotIncreasing):
                errorIndication = None
            if errorIndication or errorStatus:
                yield errorIndication, errorStatus, errorIndex, (
                    varBindTable[0] if varBindTable else []
                )
                return

            stopFlag = False
            for row, rowVarBinds in enumerate(varBindTable):
                previousVarBinds = varBinds if row == 0 else varBindTable[row - 1]
                for column, (name, value) in enumerate(rowVarBinds):
                    if (
                        nullVarBinds[column]
                        or isinstance(value, Null)
                        or (not lexicographicMode and not initialVars[column].isPrefixOf(name))
                    ):
                        rowVarBinds[column] = previousVarBinds[column][0], endOfMibView
                        nullVarBinds[column] = True
                if all(value is endOfMibView for _, value in rowVarBinds):
                    varBindTable = varBindTable[:row]
                    stopFlag = True
                    break

            totalRows += len(varBindTable)
            totalCalls += 1
            for rowVarBinds in varBindTable:
                nextVarBinds = yield errorIndication, errorStatus, errorIndex, rowVarBinds
                if nextVarBinds:
                    varBinds = nextVarBinds
                    initialVars = [x[0] for x in vbProcessor.makeVarBinds(snmpEngine, varBinds)]
                    nullVarBinds = [False] * len(initialVars)
                    break
            else:
                varBinds = varBindTable[-1] if varBindTable else []

            if (
                stopFlag
                or (maxRows and totalRows >= maxRows)
                or (maxCalls and totalCalls >= maxCalls)
            ):
                return
    finally:
        _close(loop, snmpEngine)
        asyncio.set_event_loop(None)
