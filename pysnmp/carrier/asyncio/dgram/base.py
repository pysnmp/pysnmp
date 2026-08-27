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
import socket
import sys
import traceback
from pysnmp.carrier.asyncio.base import AbstractAsyncioTransport
from pysnmp.carrier import error
from pysnmp import debug

import asyncio

class DgramAsyncioProtocol(asyncio.DatagramProtocol, AbstractAsyncioTransport):
    """Base Asyncio datagram Transport, to be used with AsyncioDispatcher"""
    sockFamily = None
    addressType = lambda x: x
    def __init__(self, sock=None, sockMap=None, loop=None):
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
        if self._cbFun is None:
            raise error.CarrierError('Unable to call cbFun')
        else:
            self.loop.call_soon(self._cbFun, self, transportAddress, datagram)

    def connection_made(self, transport):
        self.transport = transport
        sock = transport.get_extra_info('socket')
        for configureSocket in self._pendingSocketOptions:
            configureSocket(sock)
        self._pendingSocketOptions = []
        debug.logger & debug.flagIO and debug.logger('connection_made: invoked')
        while self._writeQ:
            outgoingMessage, transportAddress = self._writeQ.pop(0)
            debug.logger & debug.flagIO and debug.logger('connection_made: transportAddress %r outgoingMessage %s' %
                                                         (transportAddress, debug.hexdump(outgoingMessage)))
            try:
                self.transport.sendto(outgoingMessage, self.normalizeAddress(transportAddress))
            except Exception:
                raise error.CarrierError(';'.join(traceback.format_exception(*sys.exc_info())))

    def connection_lost(self, exc):
        self.transport = None
        debug.logger & debug.flagIO and debug.logger('connection_lost: invoked')

    # AbstractAsyncioTransport API

    def openClientMode(self, iface=None):
        try:
            c = self.loop.create_datagram_endpoint(
                lambda: self, local_addr=iface, family=self.sockFamily
            )
            if self.loop.is_running():
                self._lport = self.loop.create_task(c)
            else:
                self.loop.run_until_complete(c)
        except Exception:
            raise error.CarrierError(';'.join(traceback.format_exception(*sys.exc_info())))
        return self

    def openServerMode(self, iface):
        try:
            c = self.loop.create_datagram_endpoint(
                lambda: self, local_addr=iface, family=self.sockFamily
            )
            if self.loop.is_running():
                self._lport = self.loop.create_task(c)
            else:
                self.loop.run_until_complete(c)
        except Exception:
            raise error.CarrierError(';'.join(traceback.format_exception(*sys.exc_info())))
        return self

    def closeTransport(self):
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
        debug.logger & debug.flagIO and debug.logger('sendMessage: {} transportAddress {!r} outgoingMessage {}'.format(
            (self.transport is None and "queuing" or "sending"),
            transportAddress, debug.hexdump(outgoingMessage)
        ))
        if self.transport is None:
            self._writeQ.append((outgoingMessage, transportAddress))
        else:
            try:
                self.transport.sendto(outgoingMessage, self.normalizeAddress(transportAddress))
            except Exception:
                raise error.CarrierError(';'.join(traceback.format_exception(*sys.exc_info())))

    def getLocalAddress(self):
        if self.transport is None:
            return None
        return self.transport.get_extra_info('sockname')

    def normalizeAddress(self, transportAddress):
        if not isinstance(transportAddress, self.addressType):
            transportAddress = self.addressType(transportAddress)
        if not transportAddress.getLocalAddress():
            transportAddress.setLocalAddress(self.getLocalAddress())
        return transportAddress

    def _configureSocket(self, configureSocket):
        if self.transport is None:
            self._pendingSocketOptions.append(configureSocket)
            return
        configureSocket(self.transport.get_extra_info('socket'))

    def enableBroadcast(self, flag=1):
        def configureSocket(sock):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, flag)

        try:
            self._configureSocket(configureSocket)
        except OSError:
            raise error.CarrierError(
                'setsockopt() for SO_BROADCAST failed: {}'.format(
                    sys.exc_info()[1]
                )
            )
        return self

    def enablePktInfo(self, flag=1):
        raise error.CarrierError(
            'Packet-information source-address handling is unavailable with '
            'asyncio datagram transports; use a raw asyncio socket for this use case'
        )

    def enableTransparent(self, flag=1):
        if self.sockFamily == socket.AF_INET:
            option = socket.SOL_IP, socket.IP_TRANSPARENT
        elif self.sockFamily == socket.AF_INET6:
            option = socket.SOL_IPV6, socket.IPV6_TRANSPARENT
        else:
            raise error.CarrierError('IP_TRANSPARENT is only supported by IP datagram transports')

        def configureSocket(sock):
            sock.setsockopt(option[0], option[1], flag)

        try:
            self._configureSocket(configureSocket)
        except (AttributeError, OSError):
            raise error.CarrierError(
                'setsockopt() for IP_TRANSPARENT failed: {}'.format(
                    sys.exc_info()[1]
                )
            )
        return self
