"""SNMP over TCP (:RFC:`3430`): framing, connection handling and end-to-end use.

The framing tests are the substantive ones. A datagram carries exactly one
message and the socket says where it ends; a stream says nothing, so a receiver
has to find the boundaries itself -- and the two cases it has to survive are a
message split across reads and several messages arriving in one.
"""

import asyncio
import functools
import socket

import pytest

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.stream import tcp, tcp6
from pysnmp.carrier.asyncio.stream.base import (
    SnmpStreamProtocol,
    StreamFramingError,
    decodeMessageLength,
)
from pysnmp.carrier.error import CarrierError
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Tcp6TransportTarget,
    TcpTransportTarget,
    bulkCmd,
    getCmd,
    nextCmd,
)

SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"


def oidOf(varBind):
    """The numeric OID of a varbind, whatever name the MIB resolved it to."""
    return str(varBind[0].getOid())


def berMessage(body):
    """A BER SEQUENCE wrapping `body`, which is what an SNMP message looks like."""
    length = len(body)
    if length < 0x80:
        header = bytes((0x30, length))
    else:
        lengthOctets = length.to_bytes((length.bit_length() + 7) // 8, "big")
        header = bytes((0x30, 0x80 | len(lengthOctets))) + lengthOctets
    return header + body


def runOnItsOwnLoop(coroutineFunction):
    """Run an `async def` test body to completion, as a plain test.

    This project has no pytest-asyncio; the tests that need a loop make one, the
    way `asyncio.run` does, so each gets a loop of its own with nothing left
    over from the test before it.
    """

    @functools.wraps(coroutineFunction)
    def test(*args, **kwargs):
        return asyncio.run(coroutineFunction(*args, **kwargs))

    return test


def freePort(kind=socket.SOCK_STREAM):
    """A loopback port nothing is listening on, by binding and letting go."""
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# --- framing --------------------------------------------------------------


def test_short_form_length_is_the_octet_itself():
    assert decodeMessageLength(berMessage(b"x" * 5)) == 7


def test_long_form_length_spans_the_octets_it_declares():
    message = berMessage(b"x" * 300)
    # 0x30, 0x82, two length octets, then the body.
    assert message[:4] == bytes((0x30, 0x82, 0x01, 0x2C))
    assert decodeMessageLength(message) == 304


def test_header_that_has_not_arrived_yet_is_not_an_error():
    """A stream shows up a byte at a time; a partial header just means wait."""
    assert decodeMessageLength(b"") is None
    assert decodeMessageLength(b"\x30") is None
    # Long form promising two length octets, with only one of them here.
    assert decodeMessageLength(b"\x30\x82\x01") is None


def test_length_is_known_before_the_body_arrives():
    """Which is what lets a receiver know how much more to wait for."""
    assert decodeMessageLength(berMessage(b"x" * 300)[:4]) == 304


def test_something_that_is_not_a_sequence_is_not_framable():
    with pytest.raises(StreamFramingError, match="Not an SNMP message"):
        decodeMessageLength(b"\x04\x05hello")


def test_indefinite_length_is_refused():
    """There is no length field to frame on, which RFC 3430 section 3 requires."""
    with pytest.raises(StreamFramingError, match="Indefinite-length"):
        decodeMessageLength(b"\x30\x80\x02\x01\x00")


def test_reserved_length_form_is_refused():
    with pytest.raises(StreamFramingError, match="Reserved BER length form"):
        decodeMessageLength(b"\x30\xff\x01")


def test_declared_length_beyond_the_limit_is_refused_before_buffering():
    """A peer needs only to claim a size to make a receiver hold it, so it cannot.

    The claim is in the header, which is why this is caught from the length
    octets alone rather than after the body has been read.
    """
    claimsAHundredMegabytes = bytes((0x30, 0x84)) + (100 * 1024 * 1024).to_bytes(
        4, "big"
    )

    with pytest.raises(StreamFramingError, match="exceeds"):
        decodeMessageLength(claimsAHundredMegabytes, maxMessageSize=1024)

    # A message within the limit is unaffected.
    assert decodeMessageLength(berMessage(b"x" * 10), maxMessageSize=1024) == 12


# --- what the framing is for, at the protocol level -----------------------


class RecordingCarrier:
    """Stands in for the transport, recording what the protocol hands it."""

    maxMessageSize = 64 * 1024

    def __init__(self):
        self.messages = []
        self.errors = []
        self.closed = []

    def normalizeAddress(self, transportAddress):
        return tcp.TcpTransportAddress(transportAddress)

    def _connectionMade(self, protocol):
        pass

    def _connectionLost(self, protocol, exc):
        pass

    def _messageReceived(self, protocol, incomingMessage):
        self.messages.append(incomingMessage)

    def _connectionFailed(self, protocol, exc):
        self.closed.append(protocol)
        self.errors.append(exc)


class FakeSocketTransport:
    """The little of `asyncio.Transport` a protocol under test touches."""

    def __init__(self):
        self.written = b""
        self.closed = False

    def get_extra_info(self, name, default=None):
        return {"sockname": ("127.0.0.1", 1161), "peername": ("127.0.0.1", 40000)}.get(
            name, default
        )

    def write(self, data):
        self.written += data

    def is_closing(self):
        return self.closed

    def close(self):
        self.closed = True

    def abort(self):
        self.closed = True


def connectedProtocol():
    carrier = RecordingCarrier()
    protocol = SnmpStreamProtocol(carrier)
    protocol.connection_made(FakeSocketTransport())
    return carrier, protocol


def test_message_split_across_reads_is_reassembled():
    carrier, protocol = connectedProtocol()
    message = berMessage(b"payload" * 40)

    for offset in range(0, len(message), 7):
        protocol.data_received(message[offset : offset + 7])

    assert carrier.messages == [message]


def test_a_read_that_stops_mid_header_is_held_over():
    carrier, protocol = connectedProtocol()
    message = berMessage(b"x" * 300)

    protocol.data_received(message[:1])
    assert carrier.messages == []
    protocol.data_received(message[1:3])
    assert carrier.messages == []
    protocol.data_received(message[3:])
    assert carrier.messages == [message]


def test_several_messages_in_one_read_are_all_delivered():
    carrier, protocol = connectedProtocol()
    messages = [berMessage(b"one"), berMessage(b"two" * 100), berMessage(b"three")]

    protocol.data_received(b"".join(messages))

    assert carrier.messages == messages


def test_a_trailing_partial_message_waits_for_the_rest():
    carrier, protocol = connectedProtocol()
    whole = berMessage(b"whole")
    partial = berMessage(b"partial message")

    protocol.data_received(whole + partial[:4])
    assert carrier.messages == [whole]

    protocol.data_received(partial[4:])
    assert carrier.messages == [whole, partial]


def test_unframable_bytes_give_the_connection_up():
    """The boundary is what was lost, so there is no offset to resume at."""
    carrier, protocol = connectedProtocol()

    protocol.data_received(b"GET / HTTP/1.1\r\n")

    assert carrier.messages == []
    assert carrier.closed == [protocol]
    assert isinstance(carrier.errors[0], StreamFramingError)


def test_a_message_larger_than_the_limit_gives_the_connection_up():
    carrier, protocol = connectedProtocol()

    protocol.data_received(bytes((0x30, 0x84)) + (1 << 30).to_bytes(4, "big"))

    assert carrier.messages == []
    assert carrier.closed == [protocol]
    assert "exceeds" in str(carrier.errors[0])


def test_the_carrier_closes_a_connection_it_gave_up_on_and_says_why():
    """The other half of the two tests above: what the real carrier then does."""
    reported = []

    transport = tcp.TcpTransport().openClientMode()
    transport.registerErrorCbFun(
        lambda carrier, transportAddress, transportError: reported.append(
            (transportAddress, transportError)
        )
    )

    protocol = SnmpStreamProtocol(transport, tcp.TcpTransportAddress(("127.0.0.1", 1)))
    protocol.transport = FakeSocketTransport()

    try:
        transport._connectionFailed(protocol, StreamFramingError("unframable"))
        # The error callback is deferred to the loop, as inbound messages are.
        transport.loop.run_until_complete(asyncio.sleep(0))

        assert protocol.transport.closed
        assert reported and "unframable" in str(reported[0][1])

    finally:
        transport.closeTransport()


# --- the carrier on a real socket -----------------------------------------


@runOnItsOwnLoop
async def test_client_and_server_carry_messages_both_ways():
    """A full round trip over a real connection, without an SNMP engine."""
    received = asyncio.Queue()
    answered = asyncio.Queue()

    serverTransport = tcp.TcpTransport().openServerMode(("127.0.0.1", 0))
    await asyncio.sleep(0.1)
    port = serverTransport.getLocalAddress()[1]

    def serverCb(transport, transportAddress, incomingMessage):
        received.put_nowait((transportAddress, incomingMessage))
        transport.sendMessage(berMessage(b"response"), transportAddress)

    def clientCb(transport, transportAddress, incomingMessage):
        answered.put_nowait(incomingMessage)

    serverTransport.registerCbFun(serverCb)

    clientTransport = tcp.TcpTransport().openClientMode()
    clientTransport.registerCbFun(clientCb)

    try:
        clientTransport.sendMessage(berMessage(b"request"), ("127.0.0.1", port))

        _peer, request = await asyncio.wait_for(received.get(), 5)
        assert request == berMessage(b"request")

        assert await asyncio.wait_for(answered.get(), 5) == berMessage(b"response")

        # The second message reuses the connection rather than dialling again.
        clientTransport.sendMessage(berMessage(b"again"), ("127.0.0.1", port))
        _peer, request = await asyncio.wait_for(received.get(), 5)
        assert request == berMessage(b"again")
        assert len(clientTransport._connections) == 1

    finally:
        clientTransport.closeTransport()
        serverTransport.closeTransport()


@runOnItsOwnLoop
async def test_a_refused_connection_is_reported_rather_than_queued_forever():
    reported = asyncio.Queue()

    transport = tcp.TcpTransport().openClientMode()
    transport.registerCbFun(lambda *args: None)
    transport.registerErrorCbFun(
        lambda transport, transportAddress, transportError: reported.put_nowait(
            (transportAddress, transportError)
        )
    )

    try:
        transport.sendMessage(berMessage(b"request"), ("127.0.0.1", freePort()))

        transportAddress, transportError = await asyncio.wait_for(reported.get(), 5)
        assert isinstance(transportError, CarrierError)
        assert transportAddress[0] == "127.0.0.1"
        # Nothing is left holding the message that could not be sent.
        assert transport._writeQ == []

    finally:
        transport.closeTransport()


@runOnItsOwnLoop
async def test_a_peer_that_accepts_and_then_closes_fails_the_request():
    """Accepted and dropped without an answer is an answer, and a prompt one.

    Over UDP this is indistinguishable from a lost packet and costs the whole
    retry schedule. Here the close is an event the transport sees.
    """

    async def acceptAndClose(reader, writer):
        await reader.read(1)
        writer.close()

    server = await asyncio.start_server(acceptAndClose, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    loop = asyncio.get_running_loop()
    startedAt = loop.time()

    try:
        errorIndication, _errorStatus, _errorIndex, _varBinds = await getCmd(
            SnmpEngine(),
            CommunityData("public", mpModel=1),
            TcpTransportTarget(("127.0.0.1", port), timeout=10, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(SYS_DESCR)),
        )

        assert errorIndication == "transportFailure"
        assert loop.time() - startedAt < 10

    finally:
        server.close()
        await server.wait_closed()


@runOnItsOwnLoop
async def test_a_server_does_not_dial_out_to_answer_a_vanished_peer():
    """RFC 3430 section 3 puts opening the connection on the sending side."""
    transport = tcp.TcpTransport().openServerMode(("127.0.0.1", 0))
    await asyncio.sleep(0.1)

    try:
        with pytest.raises(CarrierError, match="not opened in client mode"):
            transport.sendMessage(berMessage(b"response"), ("127.0.0.1", freePort()))
    finally:
        transport.closeTransport()


@runOnItsOwnLoop
async def test_the_dispatcher_routes_a_transport_failure_to_its_error_callback():
    reported = []
    dispatcher = AsyncioDispatcher()
    transport = tcp.TcpTransport().openClientMode()

    dispatcher.registerRecvCbFun(lambda *args: None)
    dispatcher.registerErrorCbFun(
        lambda *args: reported.append(args[1:]),
    )
    dispatcher.registerTransport(tcp.domainName, transport)

    try:
        transport.sendMessage(berMessage(b"request"), ("127.0.0.1", freePort()))

        for _ in range(100):
            await asyncio.sleep(0.05)
            if reported:
                break

        assert reported, "the dispatcher never heard about the failed connection"
        transportDomain, _transportAddress, _transportError = reported[0]
        assert transportDomain == tcp.domainName

    finally:
        dispatcher.closeDispatcher()


# --- end to end, against the simulator ------------------------------------


@runOnItsOwnLoop
async def test_get_over_tcp(snmpsim_tcp_endpoint):
    engine = SnmpEngine()
    errorIndication, errorStatus, _errorIndex, varBinds = await getCmd(
        engine,
        CommunityData("public", mpModel=1),
        TcpTransportTarget(snmpsim_tcp_endpoint, timeout=5, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(SYS_DESCR)),
    )

    assert errorIndication is None
    assert errorStatus == 0
    assert oidOf(varBinds[0]) == SYS_DESCR
    assert varBinds[0][1].prettyPrint()


@runOnItsOwnLoop
async def test_getnext_over_tcp(snmpsim_tcp_endpoint):
    engine = SnmpEngine()
    errorIndication, _errorStatus, _errorIndex, varBindTable = await nextCmd(
        engine,
        CommunityData("public", mpModel=1),
        TcpTransportTarget(snmpsim_tcp_endpoint, timeout=5, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(SYS_DESCR)),
    )

    assert errorIndication is None
    assert oidOf(varBindTable[0][0]) == SYS_OBJECT_ID


@runOnItsOwnLoop
async def test_getbulk_over_tcp(snmpsim_tcp_endpoint):
    """The case TCP exists for: a reply too wide to be sure of over a datagram."""
    engine = SnmpEngine()
    errorIndication, _errorStatus, _errorIndex, varBindTable = await bulkCmd(
        engine,
        CommunityData("public", mpModel=1),
        TcpTransportTarget(snmpsim_tcp_endpoint, timeout=5, retries=1),
        ContextData(),
        0,
        20,
        ObjectType(ObjectIdentity("1.3.6.1.2.1.1")),
    )

    assert errorIndication is None
    assert len(varBindTable) > 1


@runOnItsOwnLoop
async def test_successive_requests_share_one_connection(snmpsim_tcp_endpoint):
    """Several messages on one connection, which is the framing's real exercise."""
    engine = SnmpEngine()
    target = TcpTransportTarget(snmpsim_tcp_endpoint, timeout=5, retries=1)

    for _ in range(5):
        errorIndication, _errorStatus, _errorIndex, varBinds = await getCmd(
            engine,
            CommunityData("public", mpModel=1),
            target,
            ContextData(),
            ObjectType(ObjectIdentity(SYS_DESCR)),
        )
        assert errorIndication is None
        assert varBinds[0][1].prettyPrint()

    transport = engine.transportDispatcher.getTransport(tcp.domainName)
    assert len(transport._connections) == 1


@runOnItsOwnLoop
async def test_concurrent_requests_over_tcp_all_succeed(snmpsim_tcp_endpoint):
    """Responses that arrive interleaved still frame and match up."""

    async def one_get():
        errorIndication, _errorStatus, _errorIndex, _varBinds = await getCmd(
            SnmpEngine(),
            CommunityData("public", mpModel=1),
            TcpTransportTarget(snmpsim_tcp_endpoint, timeout=5, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(SYS_DESCR)),
        )
        return errorIndication

    indications = await asyncio.gather(*(one_get() for _ in range(10)))
    assert not [i for i in indications if i is not None]


@runOnItsOwnLoop
async def test_a_refused_port_fails_the_request_instead_of_timing_out():
    """The distinction UDP cannot draw: declined to answer, or unreachable.

    The retry schedule here would take at least 20 seconds to reach
    `requestTimedOut`, so the assertion on elapsed time is what shows the
    failure came from the transport rather than from waiting it out.
    """
    loop = asyncio.get_running_loop()
    startedAt = loop.time()

    errorIndication, _errorStatus, _errorIndex, _varBinds = await getCmd(
        SnmpEngine(),
        CommunityData("public", mpModel=1),
        TcpTransportTarget(("127.0.0.1", freePort()), timeout=10, retries=2),
        ContextData(),
        ObjectType(ObjectIdentity(SYS_DESCR)),
    )

    assert errorIndication == "transportFailure"
    assert loop.time() - startedAt < 10


# --- TCP over IPv6 --------------------------------------------------------


def ipv6IsUsable():
    """Whether this host can actually make an IPv6 loopback connection."""
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.bind(("::1", 0))
    except OSError:
        return False
    return True


@pytest.mark.skipif(not ipv6IsUsable(), reason="No usable IPv6 loopback on this host")
@runOnItsOwnLoop
async def test_tcp6_carries_messages_over_the_ipv6_loopback():
    received = asyncio.Queue()

    serverTransport = tcp6.Tcp6Transport().openServerMode(("::1", 0))
    await asyncio.sleep(0.1)
    port = serverTransport.getLocalAddress()[1]

    serverTransport.registerCbFun(
        lambda transport, transportAddress, incomingMessage: received.put_nowait(
            incomingMessage
        )
    )

    clientTransport = tcp6.Tcp6Transport().openClientMode()
    clientTransport.registerCbFun(lambda *args: None)

    try:
        clientTransport.sendMessage(berMessage(b"request"), ("::1", port))
        assert await asyncio.wait_for(received.get(), 5) == berMessage(b"request")

    finally:
        clientTransport.closeTransport()
        serverTransport.closeTransport()


def test_the_registered_transport_domains_are_the_rfc_3419_ones():
    """RFC 3430 defines no domain of its own and takes the TRANSPORT-ADDRESS-MIB's."""
    assert tcp.domainName == (1, 3, 6, 1, 2, 1, 100, 1, 5)
    assert tcp6.domainName == (1, 3, 6, 1, 2, 1, 100, 1, 6)
    assert tcp.snmpTCPDomain == tcp.transportDomainTcpIpv4
    assert tcp6.snmpTCP6Domain == tcp6.transportDomainTcpIpv6


def test_a_tcp_target_resolves_to_a_stream_transport():
    target = TcpTransportTarget(("127.0.0.1", 161))
    assert target.transportAddr == ("127.0.0.1", 161)
    assert target.transportDomain == tcp.domainName
    assert target.protoTransport is tcp.TcpAsyncioTransport


@pytest.mark.skipif(not socket.has_ipv6, reason="No IPv6 support on this host")
def test_a_tcp6_target_resolves_to_a_stream_transport():
    target = Tcp6TransportTarget(("::1", 161))
    assert target.transportAddr == ("::1", 161)
    assert target.transportDomain == tcp6.domainName


# --- one agent, two transports --------------------------------------------
# Serving UDP and TCP at once is the ordinary way to offer the RFC 3430
# mapping alongside the datagram one, and it is what made the dispatcher's
# loop handling matter.


def test_an_agent_can_serve_udp_and_tcp_on_one_dispatcher():
    loop = asyncio.new_event_loop()
    dispatcher = AsyncioDispatcher(loop=loop)

    try:
        dispatcher.registerTransport(
            udp.domainName,
            udp.UdpTransport(loop=loop).openServerMode(("127.0.0.1", 0)),
        )
        dispatcher.registerTransport(
            tcp.domainName,
            tcp.TcpTransport(loop=loop).openServerMode(("127.0.0.1", 0)),
        )

        assert dispatcher.getTransport(udp.domainName).loop is loop
        assert dispatcher.getTransport(tcp.domainName).loop is loop

    finally:
        dispatcher.closeDispatcher()
        loop.close()


def test_a_transport_on_another_loop_is_refused_rather_than_going_deaf():
    """Adopting its loop would leave the transport already registered unread.

    Its socket would stay open on a loop nothing runs again -- deafness with
    no error anywhere, which is far worse to diagnose than this.
    """
    loop = asyncio.new_event_loop()
    dispatcher = AsyncioDispatcher(loop=loop)

    try:
        dispatcher.registerTransport(
            udp.domainName,
            udp.UdpTransport(loop=loop).openServerMode(("127.0.0.1", 0)),
        )

        # No loop argument, and none running: this transport makes its own.
        strayTransport = tcp.TcpTransport()
        assert strayTransport.loop is not loop

        with pytest.raises(CarrierError, match="share its loop"):
            dispatcher.registerTransport(tcp.domainName, strayTransport)

        # The transport that was already there is untouched.
        assert dispatcher.getTransport(udp.domainName).loop is loop

    finally:
        dispatcher.closeDispatcher()
        loop.close()
