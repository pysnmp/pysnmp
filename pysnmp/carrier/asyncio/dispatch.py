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
import asyncio
import traceback

from pysnmp.carrier.base import AbstractTransportDispatcher
from pysnmp.error import PySnmpError


class AsyncioDispatcher(AbstractTransportDispatcher):
    """AsyncioDispatcher based on asyncio event loop"""

    def __init__(self, *args, **kwargs):
        AbstractTransportDispatcher.__init__(self)
        self.__transportCount = 0
        if 'timeout' in kwargs:
            self.setTimerResolution(kwargs['timeout'])
        self.loopingcall = None
        self._timerStartHandle = None
        self.loop = kwargs.pop('loop', None)
        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()

    async def handle_timeout(self):
        while True:
            await asyncio.sleep(self.getTimerResolution())
            self.handleTimerTick(self.loop.time())

    def _start_timer(self):
        self._timerStartHandle = None
        if self.loopingcall is None:
            self.loopingcall = self.loop.create_task(self.handle_timeout())

    def runDispatcher(self, timeout=0.0):
        if self.loop.is_running():
            return

        async def run_pending_jobs():
            while self.jobsArePending() or self.transportsAreWorking():
                await asyncio.sleep(timeout or self.getTimerResolution())

        try:
            if self.jobsArePending() or self.transportsAreWorking():
                self.loop.run_until_complete(run_pending_jobs())
            else:
                # Server mode: run the event loop indefinitely so that
                # registered transports can receive incoming messages.
                self.loop.run_forever()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            raise PySnmpError(';'.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def transportsAreWorking(self):
        for transport in self._AbstractTransportDispatcher__transports.values():
            if getattr(transport, '_writeQ', None):
                return True
        return False

    def registerTransport(self, tDomain, transport):
        # If the transport already has an event loop (e.g. server-mode
        # transport created before the dispatcher), adopt its loop so
        # that datagram reception works on the same loop.
        transportLoop = getattr(transport, 'loop', None)
        if transportLoop is not None and not self.loop.is_running():
            if transportLoop is not self.loop:
                self.loop = transportLoop

        if (
            self.loopingcall is None
            and self._timerStartHandle is None
            and self.getTimerResolution() > 0
        ):
            if self.loop.is_running():
                self._start_timer()
            else:
                self._timerStartHandle = self.loop.call_soon(self._start_timer)
        AbstractTransportDispatcher.registerTransport(self, tDomain, transport)
        self.__transportCount += 1

    def _cancel_timer(self):
        if self._timerStartHandle is not None:
            self._timerStartHandle.cancel()
            self._timerStartHandle = None
        if self.loopingcall is None:
            return
        self.loopingcall.cancel()
        if not self.loop.is_running():
            self.loop.run_until_complete(asyncio.gather(self.loopingcall, return_exceptions=True))
        self.loopingcall = None

    def unregisterTransport(self, tDomain):
        t = AbstractTransportDispatcher.getTransport(self, tDomain)
        if t is not None:
            AbstractTransportDispatcher.unregisterTransport(self, tDomain)
            self.__transportCount -= 1

        # The last transport has been removed, stop the timeout
        if self.__transportCount == 0 and (
            self.loopingcall is not None or self._timerStartHandle is not None
        ):
            self._cancel_timer()

    def closeDispatcher(self):
        AbstractTransportDispatcher.closeDispatcher(self)
        self._cancel_timer()
        self.__transportCount = 0
