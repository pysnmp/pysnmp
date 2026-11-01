"""Caller-bound datagram sockets retain their address and transfer ownership."""

import asyncio
import socket

import pytest

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.carrier.error import CarrierError


async def test_server_adopts_bound_socket_and_closes_it():
    """A caller-bound UDP endpoint receives data and closes with its transport."""
    loop = asyncio.get_running_loop()
    received = loop.create_future()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    address = sock.getsockname()
    transport = udp.UdpAsyncioTransport(loop=loop)
    transport.registerCbFun(lambda _, peer, data: received.set_result((peer, data)))
    try:
        assert transport.openServerMode(sock=sock) is transport
        await transport._lport
        assert transport.getLocalAddress() == address
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(b"request", address)
            peer, data = await asyncio.wait_for(received, 1)
            assert peer[1] == sender.getsockname()[1]
            assert peer[0] == "127.0.0.1"
            assert data == b"request"
        transport.closeTransport()
        await asyncio.sleep(0)
        assert sock.fileno() == -1
    finally:
        transport.closeTransport()
        await asyncio.sleep(0)
        sock.close()


def test_server_adopts_socket_on_stopped_loop():
    """The synchronous opening path also adopts and closes the given socket."""
    loop = asyncio.new_event_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    transport = udp.UdpAsyncioTransport(loop=loop)
    try:
        transport.openServerMode(sock=sock)
        assert transport.getLocalAddress() == sock.getsockname()
        transport.closeTransport()
        loop.run_until_complete(asyncio.sleep(0))
        assert sock.fileno() == -1
    finally:
        sock.close()
        loop.close()


def test_server_rejects_wrong_socket_type():
    """Reject a stream socket before scheduling or taking its ownership."""
    loop = asyncio.new_event_loop()
    transport = udp.UdpAsyncioTransport(loop=loop)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            with pytest.raises(CarrierError, match="SOCK_DGRAM"):
                transport.openServerMode(sock=sock)
            assert sock.fileno() >= 0
    finally:
        loop.close()


@pytest.mark.skipif(not socket.has_ipv6, reason="IPv6 is unavailable")
def test_server_rejects_wrong_socket_family():
    """An IPv4 transport rejects an IPv6 socket with a family diagnostic."""
    loop = asyncio.new_event_loop()
    transport = udp.UdpAsyncioTransport(loop=loop)
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as sock:
            with pytest.raises(CarrierError, match="family"):
                transport.openServerMode(sock=sock)
            assert sock.fileno() >= 0
    finally:
        loop.close()


def test_server_requires_address_or_socket():
    """Omitting both inputs raises CarrierError rather than an asyncio error."""
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(CarrierError, match="iface or sock"):
            udp.UdpAsyncioTransport(loop=loop).openServerMode()
    finally:
        loop.close()


def test_server_rejects_address_and_socket():
    """Ambiguous binding inputs leave the caller's socket untouched."""
    loop = asyncio.new_event_loop()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            with pytest.raises(CarrierError, match="iface or sock"):
                udp.UdpAsyncioTransport(loop=loop).openServerMode(
                    ("127.0.0.1", 0), sock=sock
                )
            assert sock.fileno() >= 0
    finally:
        loop.close()


def test_snmp_poll_uses_a_caller_bound_socket(monkeypatch):
    """An SNMP GET crosses an adopted loopback socket and returns sysDescr.0."""
    from tests.end_to_end import SYS_DESCR, pollRoundTrip

    open_server = udp.UdpAsyncioTransport.openServerMode
    adopted = []

    def adopt(transport, iface):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(iface)
        adopted.append(sock)
        return open_server(transport, sock=sock)

    monkeypatch.setattr(udp.UdpAsyncioTransport, "openServerMode", adopt)
    try:
        bindings = pollRoundTrip()
        assert bindings[0][0] == SYS_DESCR
        assert adopted
        assert all(sock.fileno() == -1 for sock in adopted)
    finally:
        for sock in adopted:
            sock.close()
