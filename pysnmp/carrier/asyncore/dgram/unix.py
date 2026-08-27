"""Deprecated compatibility imports for asyncio Unix datagram transport."""

from pysnmp.carrier.asyncio.dgram.unix import *

UnixSocketTransport = UnixAsyncioTransport
UnixTransport = UnixAsyncioTransport
