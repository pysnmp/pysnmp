#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""SNMP over TCP/IPv6, transport domain 1.3.6.1.2.1.100.1.6.

``transportDomainTcpIpv6`` from the TRANSPORT-ADDRESS-MIB (:RFC:`3419`), which
is where :RFC:`3430` takes its domains from. See `pysnmp.carrier.asyncio.stream.tcp`
for why that registration rather than either of the pre-standard ones.
"""

import socket

from pysnmp.carrier.asyncio.stream.base import StreamAsyncioTransport
from pysnmp.carrier.base import AbstractTransportAddress

#: ``transportDomainTcpIpv6``, TRANSPORT-ADDRESS-MIB (:RFC:`3419#section-3`).
domainName = snmpTCP6Domain = transportDomainTcpIpv6 = (1, 3, 6, 1, 2, 1, 100, 1, 6)


class Tcp6TransportAddress(tuple, AbstractTransportAddress):
    """An IPv6 endpoint, as the `(host, port)` pair a caller names it by.

    Two parts rather than the four a sockaddr has, and a zone rides in the host
    string in the :RFC:`4007#section-11` `%` form. A stream transport can keep
    it that way where the datagram one cannot: `create_connection` resolves the
    host itself, zone and all, whereas `sendto` needs a scope ID already
    resolved into the sockaddr.
    """

    pass


class Tcp6AsyncioTransport(StreamAsyncioTransport):
    """SNMP over TCP/IPv6."""

    sockFamily = socket.AF_INET6 if socket.has_ipv6 else None
    addressType = Tcp6TransportAddress
    unboundLocalAddress = ("::", 0, 0, 0)


Tcp6Transport = Tcp6AsyncioTransport
