"""Blocking trap and inform delivery."""

import asyncio

from pysnmp._aliases import install as _installAliases
from pysnmp.hlapi.asyncio import ntforg

__all__ = ["send_notification"]


def send_notification(
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
                ntforg.send_notification(
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


#: The camelCase spelling this name used to have. Served by ``__getattr__``
#: below rather than bound here, so that using it warns -- see
#: :py:mod:`pysnmp._aliases`.
_DEPRECATED_ALIASES = {"sendNotification": "send_notification"}

__getattr__, __dir__ = _installAliases(__name__, globals(), _DEPRECATED_ALIASES)
