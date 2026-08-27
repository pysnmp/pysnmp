"""Deprecated compatibility imports for asyncio datagram transports."""

from pysnmp.carrier.asyncio.dgram.base import DgramAsyncioProtocol

DgramSocketTransport = DgramAsyncioProtocol
