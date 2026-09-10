"""Blocking trap and inform delivery."""

import asyncio

from pysnmp.hlapi.asyncio import ntforg

__all__ = ["sendNotification"]


def sendNotification(
    snmpEngine, authData, transportTarget, contextData, notifyType, varBinds, **options
):
    """Blocking trap or inform delivery.

    Runs on an event loop of its own, so it is usable from code that has none;
    calling it from inside a running loop raises rather than deadlocking.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    else:
        raise RuntimeError(
            "The synchronous HLAPI cannot run while an asyncio event loop is running; "
            "use pysnmp.hlapi.asyncio instead"
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
