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
        if iface is None:
            fd, iface = tempfile.mkstemp(prefix="pysnmp-", dir=tempfile.gettempdir())
            os.close(fd)
        if Path(iface).exists():
            Path(iface).unlink()
        self._iface = iface
        return DgramAsyncioProtocol.openClientMode(self, iface)

    def openServerMode(self, iface):
        if Path(iface).exists():
            Path(iface).unlink()
        self._iface = iface
        return DgramAsyncioProtocol.openServerMode(self, iface)

    def closeTransport(self):
        DgramAsyncioProtocol.closeTransport(self)
        if self._iface:
            Path(self._iface).unlink(missing_ok=True)


UnixTransport = UnixAsyncioTransport
UnixDgramSocketTransport = UnixAsyncioTransport
