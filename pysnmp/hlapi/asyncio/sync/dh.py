#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Synchronous facade for the Diffie-Hellman key change helper."""

from __future__ import annotations

import asyncio
from typing import Any

from pysnmp.hlapi.asyncio import dh as _async_dh

__all__ = ["dhKeyChange", "dh_key_change"]


def dh_key_change(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    keyType: str = "auth",
    **options: Any,
) -> _async_dh.DHKeyChangeResult:
    """Synchronously call :func:`pysnmp.hlapi.asyncio.dh_key_change`."""
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
        return loop.run_until_complete(
            _async_dh.dh_key_change(
                snmpEngine,
                authData,
                transportTarget,
                contextData,
                keyType,
                **options,
            )
        )
    finally:
        if snmpEngine.transportDispatcher is not None:
            snmpEngine.transportDispatcher.closeDispatcher()
            loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        asyncio.set_event_loop(None)


# Preserve the camel-case spelling used by this branch's legacy HLAPI.
dhKeyChange = dh_key_change
