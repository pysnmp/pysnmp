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
"""What every asyncio transport shares: the loop it runs on and its lifecycle."""

from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.base import AbstractTransport
from pysnmp.carrier.error import CarrierError


class AbstractAsyncioTransport(AbstractTransport):
    """What every asyncio transport shares, to be used with `AsyncioDispatcher`."""

    protoTransportDispatcher = AsyncioDispatcher

    def _checkLoopIsUsable(self) -> None:
        """Refuse to open a socket on an event loop that has been closed.

        A transport keeps the loop it was built on. Reusing it after that loop was
        closed -- which is what tearing down the engine it was built for does --
        fails inside asyncio with `Event loop is closed`, wrapped by the callers
        here in a formatted traceback that says nothing about the cause. Say what
        happened instead.
        """
        loop = getattr(self, "loop", None)
        if loop is not None and loop.is_closed():
            raise CarrierError(
                f"Transport {self!r} is bound to an asyncio event loop that has "
                f"already been closed, so no socket can be opened on it. This "
                f"usually means the transport outlived the engine it was built "
                f"for. Build a new transport, or pass a live loop=... to this one."
            )
