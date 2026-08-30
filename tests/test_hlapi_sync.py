"""Unit tests for synchronous asyncio HLAPI helpers."""

import asyncio

import pytest

from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.asyncio.sync import ntforg


def test_notification_restores_existing_event_loop():
    existing_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(existing_loop)
    try:
        notification = ntforg.sendNotification(SnmpEngine(), None, None, None, None, [])
        with pytest.raises(StopIteration):
            next(notification)

        assert asyncio.get_event_loop() is existing_loop
        assert not existing_loop.is_closed()
    finally:
        asyncio.set_event_loop(None)
        existing_loop.close()
