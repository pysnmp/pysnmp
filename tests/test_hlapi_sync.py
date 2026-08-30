"""Unit tests for synchronous asyncio HLAPI helpers."""

import asyncio

import pytest

from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.asyncio.sync import ntforg


def test_notification_restores_event_loop_state():
    existing_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(existing_loop)
    try:
        notification = ntforg.sendNotification(SnmpEngine(), None, None, None, None, [])
        with pytest.raises(StopIteration):
            next(notification)

        # The sync facade creates its own loop and restores None on cleanup,
        # matching the behaviour of cmdgen and device sync facades. After
        # set_event_loop(None), get_event_loop() raises RuntimeError on
        # Python 3.12+ (and returns None on older versions).
        try:
            current_loop = asyncio.get_event_loop()
        except RuntimeError:
            current_loop = None
        assert current_loop is None
        assert not existing_loop.is_closed()
    finally:
        asyncio.set_event_loop(None)
        existing_loop.close()
