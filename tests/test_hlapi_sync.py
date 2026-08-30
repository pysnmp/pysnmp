"""Unit tests for synchronous asyncio HLAPI helpers."""

import asyncio
import warnings

import pytest

from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.asyncio.sync import ntforg


def test_notification_restores_existing_event_loop():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        try:
            previous_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            previous_loop = None
    existing_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(existing_loop)
    try:
        notification = ntforg.sendNotification(SnmpEngine(), None, None, None, None, [])
        with pytest.raises(StopIteration):
            next(notification)

        assert asyncio.get_event_loop() is existing_loop
        assert not existing_loop.is_closed()
    finally:
        asyncio.set_event_loop(previous_loop)
        existing_loop.close()
