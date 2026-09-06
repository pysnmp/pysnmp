import asyncio

from pysnmp.carrier.asyncio.dgram.udp import UdpAsyncioTransport, UdpTransportAddress
from pysnmp.carrier.asyncio.dgram.udp6 import Udp6AsyncioTransport, Udp6TransportAddress


class _DummyTransport:
    def __init__(self, sockname):
        self._sockname = sockname

    def get_extra_info(self, name):
        assert name == "sockname"
        return self._sockname


def test_get_local_address_defaults_for_unbound_udp_transport():
    loop = asyncio.new_event_loop()
    try:
        transport = UdpAsyncioTransport(loop=loop)
        transport.transport = _DummyTransport(None)
        assert transport.getLocalAddress() == ("0.0.0.0", 0)
    finally:
        loop.close()


def test_get_local_address_defaults_for_unbound_udp6_transport():
    loop = asyncio.new_event_loop()
    try:
        transport = Udp6AsyncioTransport(loop=loop)
        transport.transport = _DummyTransport(None)
        assert transport.getLocalAddress() == ("::", 0, 0, 0)
    finally:
        loop.close()


def test_normalize_address_sets_default_local_address_for_udp():
    loop = asyncio.new_event_loop()
    try:
        transport = UdpAsyncioTransport(loop=loop)
        transport.transport = _DummyTransport(None)
        transport_address = UdpTransportAddress(("127.0.0.1", 161))
        normalized_address = transport.normalizeAddress(transport_address)
        assert normalized_address.getLocalAddress() == ("0.0.0.0", 0)
    finally:
        loop.close()


def test_udp6_normalize_address_preserves_existing_local_address():
    loop = asyncio.new_event_loop()
    try:
        transport = Udp6AsyncioTransport(loop=loop)
        transport.transport = _DummyTransport(None)
        local_address = ("::1", 12345, 0, 0)
        transport_address = Udp6TransportAddress(("fe80::1%eth0", 161, 0, 0)).setLocalAddress(local_address)
        normalized_address = transport.normalizeAddress(transport_address)
        assert normalized_address == ("fe80::1", 161, 0, 0)
        assert normalized_address.getLocalAddress() == local_address
    finally:
        loop.close()
