#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# Copyright (C) 2014, Zebra Technologies
# Authors: Matt Hooks <me@matthooks.com>
#          Zachary Lorusso <zlorusso@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
#
"""The datagram protocol every connectionless asyncio transport is built on.

Handles the parts that do not vary with address family: opening the socket,
queueing sends until the loop connects it, and handing what arrives to the
callback the dispatcher registered.
"""

import asyncio
import socket
import traceback

from pysnmp import debug
from pysnmp.carrier import error
from pysnmp.carrier.asyncio.base import AbstractAsyncioTransport


class DgramAsyncioProtocol(asyncio.DatagramProtocol, AbstractAsyncioTransport):
    """Base Asyncio datagram Transport, to be used with AsyncioDispatcher."""

    #: Address family this transport opens sockets in. None where the
    #: platform has no such family -- AF_UNIX on Windows, AF_INET6 on a build
    #: without IPv6 -- in which case the transport cannot be opened at all.
    sockFamily: "socket.AddressFamily | None" = None

    #: Local address to report for a socket the platform declines to name.
    #: An endpoint opened with no local address is left unbound, and there the
    #: platforms disagree: POSIX answers getsockname() with the family's
    #: wildcard, Windows fails it and asyncio turns that into a None sockname.
    #: Concrete transports name their wildcard here so getLocalAddress() gives
    #: the same answer everywhere; None where the family has no wildcard.
    unboundLocalAddress: "tuple | str | None" = None

    def __init__(self, sock=None, sockMap=None, loop=None):
        """Binds to an event loop now, creating one where there is no running loop.

        Writes are queued rather than sent, because the transport does not exist until
        asyncio has created the endpoint; socket options are queued for the same reason
        and applied to the socket once there is one.
        """
        self._writeQ = []
        self._lport = None
        self._pendingSocketOptions = []
        self.transport = None
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
        self.loop = loop

    def datagram_received(self, datagram, transportAddress):
        """Hand an arriving datagram to the dispatcher's callback, via the loop.

        Delivery is deferred with `call_soon` rather than made here, so the callback
        does not run inside asyncio's receive path.
        """
        if self._cbFun is None:
            raise error.CarrierError("Unable to call cbFun")
        else:
            self.loop.call_soon(self._cbFun, self, transportAddress, datagram)

    def connection_made(self, transport):
        """Take the socket, apply the options that were waiting, and flush the send queue.

        Socket options and sends can both be asked for before the loop has a socket to
        apply them to, so both are held until this point.
        """
        self.transport = transport
        sock = transport.get_extra_info("socket")
        for configureSocket in self._pendingSocketOptions:
            configureSocket(sock)
        self._pendingSocketOptions = []
        debug.logger & debug.flagIO and debug.logger("connection_made: invoked")
        while self._writeQ:
            outgoingMessage, transportAddress = self._writeQ.pop(0)
            debug.logger & debug.flagIO and debug.logger(
                f"connection_made: transportAddress {transportAddress!r} outgoingMessage {debug.hexdump(outgoingMessage)}"
            )
            try:
                self.transport.sendto(
                    outgoingMessage, self.normalizeAddress(transportAddress)
                )
            except Exception as e:
                raise error.CarrierError(
                    ";".join(traceback.format_exception(type(e), e, e.__traceback__))
                ) from e

    def connection_lost(self, exc):
        """Drop the transport. Sends after this queue again rather than failing."""
        self.transport = None
        debug.logger & debug.flagIO and debug.logger("connection_lost: invoked")

    # AbstractAsyncioTransport API

    def openClientMode(self, iface=None):
        """Open a socket for sending, optionally bound to a local address."""
        try:
            c = self.loop.create_datagram_endpoint(
                lambda: self, local_addr=iface, family=self.sockFamily
            )
            if self.loop.is_running():
                self._lport = self.loop.create_task(c)
            else:
                self.loop.run_until_complete(c)
        except Exception as e:
            raise error.CarrierError(
                ";".join(traceback.format_exception(type(e), e, e.__traceback__))
            ) from e
        return self

    def openServerMode(self, iface):
        """Bind a socket to receive on."""
        try:
            c = self.loop.create_datagram_endpoint(
                lambda: self, local_addr=iface, family=self.sockFamily
            )
            if self.loop.is_running():
                self._lport = self.loop.create_task(c)
            else:
                self.loop.run_until_complete(c)
        except Exception as e:
            raise error.CarrierError(
                ";".join(traceback.format_exception(type(e), e, e.__traceback__))
            ) from e
        return self

    def closeTransport(self):
        """Cancel the pending endpoint, close the socket, and drop the callback."""
        if self._lport is not None:
            self._lport.cancel()
            if not self.loop.is_running():
                self.loop.run_until_complete(
                    asyncio.gather(self._lport, return_exceptions=True)
                )
            self._lport = None
        if self.transport is not None:
            self.transport.close()
        AbstractAsyncioTransport.closeTransport(self)

    def sendMessage(self, outgoingMessage, transportAddress):
        """Send a datagram, queueing it if the loop has not connected the socket yet."""
        debug.logger & debug.flagIO and debug.logger(
            "sendMessage: {} transportAddress {!r} outgoingMessage {}".format(
                (self.transport is None and "queuing" or "sending"),
                transportAddress,
                debug.hexdump(outgoingMessage),
            )
        )
        if self.transport is None:
            self._writeQ.append((outgoingMessage, transportAddress))
        else:
            try:
                self.transport.sendto(
                    outgoingMessage, self.normalizeAddress(transportAddress)
                )
            except Exception as e:
                raise error.CarrierError(
                    ";".join(traceback.format_exception(type(e), e, e.__traceback__))
                ) from e

    def getLocalAddress(self):
        """The address this socket is bound to, or the wildcard where it is unbound.

        An unbound socket has no name POSIX and Windows agree on: one answers with the
        family's wildcard, the other fails and asyncio reports no name at all. The
        concrete transport's `unboundLocalAddress` stands in for the second case so
        callers get an address of the right shape either way.
        """
        if self.transport is None:
            return None
        localAddress = self.transport.get_extra_info("sockname")
        if localAddress is None:
            return self.unboundLocalAddress
        return localAddress

    def normalizeAddress(self, transportAddress):
        """Coerce to this transport's address type, noting the local address on it.

        The local address rides along so a reply can leave by the interface the request
        arrived on, which matters once a socket is bound to a wildcard.
        """
        if not isinstance(transportAddress, self.addressType):
            transportAddress = self.addressType(transportAddress)
        if not transportAddress.getLocalAddress():
            transportAddress.setLocalAddress(self.getLocalAddress())
        return transportAddress

    def _configureSocket(self, configureSocket):
        """Apply a socket option now, or hold it until there is a socket to apply it to."""
        if self.transport is None:
            self._pendingSocketOptions.append(configureSocket)
            return
        configureSocket(self.transport.get_extra_info("socket"))

    def enableBroadcast(self, flag=1):
        """Allow sending to a broadcast address."""

        def configureSocket(sock):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, flag)

        try:
            self._configureSocket(configureSocket)
        except OSError as e:
            raise error.CarrierError(
                f"setsockopt() for SO_BROADCAST failed: {e}"
            ) from e
        return self

    def enablePktInfo(self, flag=1):
        """Always fails: asyncio's datagram transport does not expose the ancillary data.

        Recovering the address a datagram arrived on needs `recvmsg`, which asyncio's
        datagram endpoint does not surface. A raw socket is the way to do this.
        """
        raise error.CarrierError(
            "Packet-information source-address handling is unavailable with "
            "asyncio datagram transports; use a raw asyncio socket for this use case"
        )

    def enableTransparent(self, flag=1):
        """Always fails, for the same reason as `enablePktInfo`."""
        if self.sockFamily == socket.AF_INET:
            option = socket.SOL_IP, socket.IP_TRANSPARENT
        elif self.sockFamily == socket.AF_INET6:
            option = socket.SOL_IPV6, socket.IPV6_TRANSPARENT
        else:
            raise error.CarrierError(
                "IP_TRANSPARENT is only supported by IP datagram transports"
            )

        def configureSocket(sock):
            sock.setsockopt(option[0], option[1], flag)

        try:
            self._configureSocket(configureSocket)
        except (AttributeError, OSError) as e:
            raise error.CarrierError(
                f"setsockopt() for IP_TRANSPARENT failed: {e}"
            ) from e
        return self
