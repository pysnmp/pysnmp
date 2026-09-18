#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The stream protocol every connection-oriented asyncio transport is built on.

A datagram carrier is one socket serving every peer. A stream carrier is one
connection per peer, so this holds what the datagram side never needed: a table
of live connections keyed by peer address, the messages waiting on a connection
still being made, and the framing that recovers message boundaries from a byte
stream.

:RFC:`3430#section-3` puts SNMP messages back to back on one connection with
nothing between them, so a receiver finds the boundaries by reading each
message's own BER length -- which is what `decodeMessageLength` does.
"""

import asyncio
import traceback

from pysnmp import debug
from pysnmp.carrier import error
from pysnmp.carrier.asyncio.base import AbstractAsyncioTransport

#: BER identifier octet of an SNMP message: universal, constructed, SEQUENCE.
#: Every SNMP message is one, in every version, so a stream that starts with
#: anything else is not SNMP and cannot be framed.
BER_SEQUENCE = 0x30


class StreamFramingError(error.CarrierError):
    """The byte stream is not a sequence of BER-encoded SNMP messages.

    Unrecoverable by nature: the boundary between messages is what was lost, so
    there is no offset at which reading could sensibly resume.
    """


def decodeMessageLength(octets, maxMessageSize=None):
    """Total octets of the message at the head of `octets`, header included.

    `None` where the header has not fully arrived yet, which is the ordinary
    case on a stream: the caller keeps buffering and asks again. This reads only
    the identifier and length octets, so a message is measured before any of its
    body is there -- which is what lets a reader know how much more to wait for.

    Raises `StreamFramingError` where the stream cannot be framed at all.

    Parameters
    ----------
    octets : bytes
        What has arrived so far, starting at a message boundary.
    maxMessageSize : int
        Largest message to admit, or `None` for no limit. A declared length
        beyond it is refused here rather than buffered, since the declaration
        is all a peer needs to send to make a receiver hold that much memory.
    """
    if len(octets) < 2:
        return None

    if octets[0] != BER_SEQUENCE:
        raise StreamFramingError(
            f"Not an SNMP message: BER identifier 0x{octets[0]:02x}, "
            f"expected 0x{BER_SEQUENCE:02x} (constructed SEQUENCE)"
        )

    lengthOctet = octets[1]

    # Short form: the octet is the length.
    if lengthOctet < 0x80:
        return 2 + lengthOctet

    # Indefinite form: the message ends at a sentinel instead of declaring a
    # size, so there is no length field to frame on -- and RFC 3430 section 3
    # is explicit that the length field is what separates messages here.
    if lengthOctet == 0x80:
        raise StreamFramingError(
            "Indefinite-length SNMP message cannot be framed on a stream"
        )

    if lengthOctet == 0xFF:
        raise StreamFramingError("Reserved BER length form 0xff")

    # Long form: the low seven bits count the octets the length is spread over.
    countOfLengthOctets = lengthOctet & 0x7F
    if len(octets) < 2 + countOfLengthOctets:
        return None

    totalLength = (
        2
        + countOfLengthOctets
        + int.from_bytes(octets[2 : 2 + countOfLengthOctets], "big")
    )

    if maxMessageSize is not None and totalLength > maxMessageSize:
        raise StreamFramingError(
            f"SNMP message of {totalLength} octets exceeds the "
            f"{maxMessageSize} octets this transport accepts"
        )

    return totalLength


class SnmpStreamProtocol(asyncio.Protocol):
    """One connection: frames what arrives on it, writes what goes out.

    Owned by the carrier, which is the object the dispatcher knows about. One
    of these exists per connection and does not outlive it.
    """

    def __init__(self, carrier, transportAddress=None):
        """`transportAddress` names the peer for a connection we opened.

        A connection this process dialled is known by the address it was asked
        for, not by what `getpeername()` reports: those differ in shape for
        IPv6, where a caller says `(host, port)` and the socket answers with a
        four-part sockaddr, and the dispatcher has to match the address a reply
        arrives on against the one a request was sent to. An accepted
        connection has no such prior address and takes the peer's.
        """
        self._carrier = carrier
        self._buffer = bytearray()
        self.transport = None
        self.transportAddress = transportAddress
        self.localAddress = None

    @property
    def isOpen(self):
        """Whether this connection can still carry a message."""
        return self.transport is not None and not self.transport.is_closing()

    def connection_made(self, transport):
        """Take the socket, learn both addresses, and let the carrier flush."""
        self.transport = transport
        self.localAddress = transport.get_extra_info("sockname")

        if self.transportAddress is None:
            self.transportAddress = self._carrier.normalizeAddress(
                transport.get_extra_info("peername")
            )

        self.transportAddress.setLocalAddress(self.localAddress)

        debug.logger & debug.flagIO and debug.logger(
            f"connection_made: peer {self.transportAddress!r} "
            f"local {self.localAddress!r}"
        )

        self._carrier._connectionMade(self)

    def data_received(self, data):
        """Buffer what arrived and hand over every whole message it completes.

        A read holds no particular number of messages: one message may take
        several reads, and several messages may arrive in one. Both are the
        normal case on a stream, so this loops until what is left is a partial
        message and keeps that for the next read.
        """
        self._buffer += data

        while True:
            try:
                length = decodeMessageLength(self._buffer, self._carrier.maxMessageSize)

            except StreamFramingError as e:
                # Nothing after this point can be trusted to begin a message,
                # so the connection goes rather than the carrier guessing at
                # where the next one might start.
                debug.logger & debug.flagIO and debug.logger(
                    f"data_received: framing failed, dropping connection: {e}"
                )
                self._carrier._connectionFailed(self, e)
                return

            if length is None or len(self._buffer) < length:
                return

            incomingMessage = bytes(self._buffer[:length])
            del self._buffer[:length]

            debug.logger & debug.flagIO and debug.logger(
                f"data_received: transportAddress {self.transportAddress!r} "
                f"incomingMessage {debug.hexdump(incomingMessage)}"
            )

            self._carrier._messageReceived(self, incomingMessage)

    def eof_received(self):
        """Let the connection close when the peer is done writing.

        Returning false rather than keeping the socket half-open: SNMP over TCP
        has no use for sending into a peer that has stopped reading, and holding
        the socket would leak one per finished conversation.
        """
        return False

    def connection_lost(self, exc):
        """Tell the carrier this connection is gone, so it stops routing to it."""
        debug.logger & debug.flagIO and debug.logger(
            f"connection_lost: {self.transportAddress!r} exception {exc!r}"
        )
        self._carrier._connectionLost(self, exc)

    def send(self, outgoingMessage):
        """Write one message. Framing is the length already inside it."""
        self.transport.write(outgoingMessage)

    def close(self):
        """Close the socket, if it is not closing already."""
        if self.transport is not None:
            self.transport.close()


class StreamAsyncioTransport(AbstractAsyncioTransport):
    """Base asyncio stream transport, to be used with `AsyncioDispatcher`.

    One of these serves every peer of its transport domain, because that is what
    the dispatcher registers: a transport per domain, addressed per message. The
    per-peer connections live underneath, keyed by address, opened on the first
    message to an address that has none and dropped when the peer closes.
    """

    #: Address family this transport opens sockets in, as in the datagram
    #: transports. `None` where the platform has no such family.
    sockFamily: "int | None" = None

    #: Local address to report where the platform declines to name the socket;
    #: see the datagram base, which has the same problem for the same reason.
    unboundLocalAddress: "tuple | str | None" = None

    #: Largest message this transport will accept or frame.
    #:
    #: :RFC:`3430#section-3` requires at least 8192 octets and encourages more,
    #: which is the whole point of the transport -- a GETBULK reply too big for
    #: a datagram path just arrives here. A stream has no natural bound, though,
    #: so one is imposed: a peer that desynchronises, or simply lies in a length
    #: field, would otherwise have a receiver buffer whatever it claims.
    maxMessageSize = 2 * 1024 * 1024

    #: Seconds to wait for a connection to complete, or `None` to wait as long
    #: as the operating system will.
    #:
    #: An address that is filtered rather than refused answers nothing, and the
    #: default TCP connect can sit there for minutes. The request behind it has
    #: nothing to report in the meantime, so the wait is cut short here and
    #: surfaces as a transport failure instead.
    connectTimeout: "float | None" = 5

    def __init__(self, sock=None, sockMap=None, loop=None):
        """Binds to an event loop now, creating one where there is no running loop.

        `sock` and `sockMap` are accepted and ignored, as in the datagram
        transports, so the two are interchangeable at the call site.
        """
        #: Messages waiting on a connection that is still being made. Named to
        #: match the datagram transports, because `AsyncioDispatcher` reads it
        #: to decide whether a client still has work outstanding.
        self._writeQ = []
        self._connections = {}
        self._connectTasks = {}
        self._server = None
        self._serverTask = None
        self._iface = None
        self._clientMode = False

        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
        self.loop = loop

    # Connection bookkeeping, called by SnmpStreamProtocol

    def _connectionKey(self, transportAddress):
        """What connections are keyed by: the address, without its subclass.

        `AbstractTransportAddress` carries a local address that a plain tuple
        does not, and two addresses naming the same peer must land on the same
        connection whether or not they carry one.
        """
        return tuple(transportAddress)

    def _connectionMade(self, protocol):
        """Adopt a new connection and send whatever was waiting for it."""
        key = self._connectionKey(protocol.transportAddress)
        self._connections[key] = protocol

        stillWaiting = []
        for outgoingMessage, transportAddress in self._writeQ:
            if self._connectionKey(transportAddress) != key:
                stillWaiting.append((outgoingMessage, transportAddress))
                continue

            debug.logger & debug.flagIO and debug.logger(
                f"_connectionMade: transportAddress {transportAddress!r} "
                f"outgoingMessage {debug.hexdump(outgoingMessage)}"
            )
            protocol.send(outgoingMessage)

        self._writeQ = stillWaiting

    def _connectionLost(self, protocol, exc):
        """Forget a connection, and report it so nothing waits on it for an answer.

        A request already sent over this connection cannot be answered on it any
        more, whether the peer closed cleanly or the connection broke, so the
        loss is reported either way. Where nothing was outstanding to this peer
        the report comes to nothing, which is the ordinary case: a peer closing
        an idle connection is not an error.

        This is what turns "the agent accepted the connection and then dropped
        it" into an answer now rather than a timeout several retries later.
        """
        key = self._connectionKey(protocol.transportAddress)
        if self._connections.get(key) is protocol:
            del self._connections[key]

        self._discardQueuedMessages(key)

        reason = f": {exc}" if exc is not None else " by the peer"
        self._reportError(
            protocol.transportAddress,
            error.CarrierError(
                f"Connection to {protocol.transportAddress!r} closed{reason}"
            ),
        )

    def _connectionFailed(self, protocol, exc):
        """Drop a connection this end has given up on, and report why."""
        protocol.close()
        self._reportError(protocol.transportAddress, exc)

    def _messageReceived(self, protocol, incomingMessage):
        """Hand an arriving message to the dispatcher's callback, via the loop.

        Deferred with `call_soon` rather than delivered here, so the callback
        does not run inside asyncio's receive path -- as in the datagram base.
        """
        if self._cbFun is None:
            raise error.CarrierError("Unable to call cbFun")

        self.loop.call_soon(
            self._cbFun, self, protocol.transportAddress, incomingMessage
        )

    # Connecting

    def _connect(self, key, transportAddress):
        """Start connecting to an address, unless that is already under way."""
        if key in self._connectTasks:
            return

        self._connectTasks[key] = self.loop.create_task(
            self._connectAndFlush(key, transportAddress)
        )

    async def _connectAndFlush(self, key, transportAddress):
        """Open one connection. Queued messages go out from `_connectionMade`."""
        try:
            connecting = self.loop.create_connection(
                lambda: SnmpStreamProtocol(self, transportAddress),
                transportAddress[0],
                transportAddress[1],
                family=self.sockFamily or 0,
                local_addr=self._iface,
            )

            if self.connectTimeout:
                await asyncio.wait_for(connecting, self.connectTimeout)
            else:
                await connecting

        except asyncio.CancelledError:
            # Shutting down, not failing: closeTransport() cancels these, and
            # the messages they were carrying are being dropped deliberately.
            raise

        except (OSError, asyncio.TimeoutError) as e:
            debug.logger & debug.flagIO and debug.logger(
                f"_connectAndFlush: {transportAddress!r} failed: {e}"
            )
            self._failQueuedMessages(
                transportAddress,
                error.CarrierError(f"Connection to {transportAddress!r} failed: {e}"),
            )

        finally:
            self._connectTasks.pop(key, None)

    def _discardQueuedMessages(self, key):
        """Drop what was waiting on a connection to an address, and say how much."""
        stillWaiting = [
            item for item in self._writeQ if self._connectionKey(item[1]) != key
        ]
        dropped = len(self._writeQ) - len(stillWaiting)
        self._writeQ = stillWaiting
        return dropped

    def _failQueuedMessages(self, transportAddress, exc):
        """Discard what was queued for an address and report the failure once.

        Reported rather than raised because there is no caller left to raise to:
        `sendMessage` returned when the message was queued, and the connection
        failed some time after that.
        """
        if self._discardQueuedMessages(self._connectionKey(transportAddress)):
            self._reportError(transportAddress, exc)

    def _reportError(self, transportAddress, exc):
        """Tell the dispatcher a peer's transport failed, if anyone is listening.

        Without this a failed connection is indistinguishable from a silent
        peer, and the request behind it waits out its full retry schedule before
        anything is said. Delivery is deferred for the same reason inbound
        messages are.
        """
        if self._errorCbFun is None:
            debug.logger & debug.flagIO and debug.logger(
                f"_reportError: no error callback, dropping {exc}"
            )
            return

        if not isinstance(exc, error.CarrierError):
            exc = error.CarrierError(str(exc))

        self.loop.call_soon(self._errorCbFun, self, transportAddress, exc)

    # AbstractAsyncioTransport API

    def openClientMode(self, iface=None):
        """Allow this transport to open connections, from `iface` if given.

        Nothing is connected here: a client has no peer until it is asked to
        send to one, and :RFC:`3430#section-3` makes opening the connection the
        sending side's job. It may be called on a transport already in server
        mode, which is how one transport both answers requests on connections
        its peers opened and originates notifications of its own.
        """
        self._iface = iface
        self._clientMode = True
        return self

    def openServerMode(self, iface):
        """Listen on `iface` for connections peers open to us."""
        try:
            listening = self.loop.create_server(
                lambda: SnmpStreamProtocol(self),
                iface[0],
                iface[1],
                family=self.sockFamily or 0,
            )

            if self.loop.is_running():
                self._serverTask = self.loop.create_task(self._startServer(listening))
            else:
                self._server = self.loop.run_until_complete(listening)

        except Exception as e:
            raise error.CarrierError(
                ";".join(traceback.format_exception(type(e), e, e.__traceback__))
            ) from e

        return self

    async def _startServer(self, listening):
        """Finish binding the listening socket, for the running-loop case."""
        self._server = await listening

    def closeTransport(self):
        """Stop listening, drop every connection, and forget what was queued."""
        for task in list(self._connectTasks.values()):
            task.cancel()

        pendingTasks = list(self._connectTasks.values())
        if self._serverTask is not None:
            self._serverTask.cancel()
            pendingTasks.append(self._serverTask)

        if pendingTasks and not self.loop.is_running():
            self.loop.run_until_complete(
                asyncio.gather(*pendingTasks, return_exceptions=True)
            )

        self._connectTasks.clear()
        self._serverTask = None

        for protocol in list(self._connections.values()):
            protocol.close()
        self._connections.clear()

        if self._server is not None:
            self._server.close()
            self._server = None

        self._writeQ = []

        AbstractAsyncioTransport.closeTransport(self)

    def sendMessage(self, outgoingMessage, transportAddress):
        """Send a message, opening a connection to the peer if there is none.

        Queued rather than sent where the connection is still being made, and
        flushed once it is. A peer that cannot be reached is reported through
        the dispatcher's error callback rather than raised, since by then this
        call has long returned.
        """
        transportAddress = self.normalizeAddress(transportAddress)
        key = self._connectionKey(transportAddress)

        connection = self._connections.get(key)
        if connection is not None and connection.isOpen:
            debug.logger & debug.flagIO and debug.logger(
                f"sendMessage: sending transportAddress {transportAddress!r} "
                f"outgoingMessage {debug.hexdump(outgoingMessage)}"
            )
            try:
                connection.send(outgoingMessage)

            except Exception as e:
                raise error.CarrierError(
                    ";".join(traceback.format_exception(type(e), e, e.__traceback__))
                ) from e

            return

        if not self._clientMode:
            # A server does not dial: the peer opened the connection, and with
            # it gone there is nothing to answer over. Connecting back to the
            # ephemeral port it used would reach nothing.
            raise error.CarrierError(
                f"No open connection to {transportAddress!r}, and this "
                f"transport was not opened in client mode"
            )

        debug.logger & debug.flagIO and debug.logger(
            f"sendMessage: queuing transportAddress {transportAddress!r} "
            f"outgoingMessage {debug.hexdump(outgoingMessage)}"
        )

        self._writeQ.append((outgoingMessage, transportAddress))
        self._connect(key, transportAddress)

    def getLocalAddress(self):
        """The address the listening socket is bound to, where there is one.

        A client-mode transport has no address of its own until it connects,
        and each of its connections has a different one, so the family's
        wildcard stands in -- which is the same answer an unbound datagram
        socket gives.
        """
        if self._server is not None and self._server.sockets:
            return self._server.sockets[0].getsockname()

        return self.unboundLocalAddress

    def normalizeAddress(self, transportAddress):
        """Coerce to this transport's address type, noting the local address."""
        if not isinstance(transportAddress, self.addressType):
            transportAddress = self.addressType(transportAddress)

        if not transportAddress.getLocalAddress():
            transportAddress.setLocalAddress(self.getLocalAddress())

        return transportAddress
