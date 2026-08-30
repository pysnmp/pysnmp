#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
import os
import tempfile
from pathlib import Path

try:
    from socket import AF_UNIX
except ImportError:
    AF_UNIX = None

from pysnmp.carrier.asyncio.dgram.base import DgramAsyncioProtocol
from pysnmp.carrier.base import AbstractTransportAddress

domainName = snmpLocalDomain = (1, 3, 6, 1, 2, 1, 100, 1, 13)


class UnixTransportAddress(str, AbstractTransportAddress):
    pass


class UnixAsyncioTransport(DgramAsyncioProtocol):
    sockFamily = AF_UNIX
    addressType = UnixTransportAddress

    def __init__(self, *args, **kwargs):
        DgramAsyncioProtocol.__init__(self, *args, **kwargs)
        self._iface = None

    def openClientMode(self, iface=None):
        if iface is None:
            fd, iface = tempfile.mkstemp(prefix='pysnmp-', dir=tempfile.gettempdir())
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
