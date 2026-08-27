"""Deprecated compatibility imports for asyncio UDP/IPv6 transport."""

from pysnmp.carrier.asyncio.dgram.udp6 import *

Udp6SocketTransport = Udp6AsyncioTransport
Udp6Transport = Udp6AsyncioTransport
