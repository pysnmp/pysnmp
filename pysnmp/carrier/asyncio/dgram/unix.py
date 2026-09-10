#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""SNMP over Unix domain datagram sockets, transport domain 1.3.6.1.2.1.100.1.13.

Not available on Windows, which has no `AF_UNIX`.
"""

import os
import socket
import tempfile
from pathlib import Path

from pysnmp.carrier.asyncio.dgram.base import DgramAsyncioProtocol
from pysnmp.carrier.base import AbstractTransportAddress

# AF_UNIX does not exist on Windows. Look it up rather than importing it, so
# the name keeps one type instead of being a constant on one platform and None
# on another.
AF_UNIX: "socket.AddressFamily | None" = getattr(socket, "AF_UNIX", None)

domainName = snmpLocalDomain = (1, 3, 6, 1, 2, 1, 100, 1, 13)


class UnixTransportAddress(str, AbstractTransportAddress):
    """A Unix domain endpoint, which is a filesystem path."""

    pass


class UnixAsyncioTransport(DgramAsyncioProtocol):
    """SNMP over Unix domain datagram sockets.

    Unavailable on Windows, where `AF_UNIX` does not exist and the constructor
    raises.
    """

    sockFamily = AF_UNIX
    addressType = UnixTransportAddress

    def __init__(self, *args, **kwargs):
        """Tracks the socket path, so a client-mode socket can be unlinked on close.

        A Unix datagram client has to bind a path of its own to receive a reply, and
        nothing else removes that file.
        """
        DgramAsyncioProtocol.__init__(self, *args, **kwargs)
        self._iface = None

    def openClientMode(self, iface=None):
        """Bind a path to send from, inventing a temporary one where none is given.

        A unix datagram socket has no reply address unless it is bound, so even a
        client needs a path of its own before it can be answered.
        """
        if iface is None:
            fd, iface = tempfile.mkstemp(prefix="pysnmp-", dir=tempfile.gettempdir())
            os.close(fd)
        if Path(iface).exists():
            Path(iface).unlink()
        self._iface = iface
        return DgramAsyncioProtocol.openClientMode(self, iface)

    def openServerMode(self, iface):
        """Bind a filesystem path to receive on, removing a stale file at that path.

        A path left behind by a previous run is not reusable and would fail the bind,
        so it is cleared rather than reported.
        """
        if Path(iface).exists():
            Path(iface).unlink()
        self._iface = iface
        return DgramAsyncioProtocol.openServerMode(self, iface)

    def closeTransport(self):
        """Close the socket and unlink the path it was bound to.

        A unix socket outlives the process that made it, so this is what stops each
        run leaving a file behind -- including the temporary path a client bound.
        """
        DgramAsyncioProtocol.closeTransport(self)
        if self._iface:
            Path(self._iface).unlink(missing_ok=True)


UnixTransport = UnixAsyncioTransport
UnixDgramSocketTransport = UnixAsyncioTransport
