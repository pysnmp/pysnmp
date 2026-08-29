#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Synchronous facade for the device-report helper."""

from __future__ import annotations

import asyncio
from typing import Any

from pysnmp.hlapi.asyncio import device as _async_device

__all__ = ["get_device_report", "getDeviceReport"]


def get_device_report(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    **options: Any,
) -> _async_device.DeviceReport:
    """Synchronously call :func:`pysnmp.hlapi.asyncio.get_device_report`."""
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
            _async_device.get_device_report(
                snmpEngine, authData, transportTarget, contextData, **options
            )
        )
    finally:
        if snmpEngine.transportDispatcher is not None:
            snmpEngine.transportDispatcher.closeDispatcher()
            loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        asyncio.set_event_loop(None)


# Preserve the camel-case spelling used by this branch's legacy HLAPI.
getDeviceReport = get_device_report
