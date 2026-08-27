"""Deprecated compatibility imports for asyncio UDP transport."""

from pysnmp.carrier.asyncio.dgram.udp import *

UdpSocketTransport = UdpAsyncioTransport
UdpTransport = UdpAsyncioTransport
