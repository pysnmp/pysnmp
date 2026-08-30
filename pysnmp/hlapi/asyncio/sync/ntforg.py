import asyncio

from pysnmp.hlapi.asyncio import ntforg

__all__ = ['sendNotification']


def sendNotification(
    snmpEngine, authData, transportTarget, contextData, notifyType, varBinds, **options
):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
<<<<<<< HEAD
        try:
            existing_loop = asyncio.get_event_loop()
        except RuntimeError:
            existing_loop = None
=======
>>>>>>> 7fd59b64 (fixfix asyncio capture)
        loop = asyncio.new_event_loop()
    else:
        raise RuntimeError(
            'The synchronous HLAPI cannot run while an asyncio event loop is running; '
            'use pysnmp.hlapi.asyncio instead'
        )

    try:
        asyncio.set_event_loop(loop)
        while varBinds:
            result = loop.run_until_complete(
                ntforg.sendNotification(
                    snmpEngine,
                    authData,
                    transportTarget,
                    contextData,
                    notifyType,
                    varBinds,
                    **options,
                )
            )
            varBinds = yield result
    finally:
        if snmpEngine.transportDispatcher is not None:
            snmpEngine.transportDispatcher.closeDispatcher()
            loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        asyncio.set_event_loop(None)
