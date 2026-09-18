#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""SNMP over TCP/IPv4, transport domain 1.3.6.1.2.1.100.1.5.

:RFC:`3430` is the transport mapping; it defines no domain OID of its own and
defers to the TRANSPORT-ADDRESS-MIB (:RFC:`3419`), whose
``transportDomainTcpIpv4`` is the value used here.

Two other OIDs name the same idea and are deliberately not used: the NMRG draft
that preceded RFC 3430 registered ``snmpTCPDomain`` as 1.3.6.1.3.91.1.1 under
the experimental arc -- Net-SNMP still uses it internally -- and NET-SNMP-TC
carries a private ``netSnmpTCPDomain`` it marks obsolete. The standard one is
what belongs in a target address table that another implementation may read.

RFC 3430 is a transport mapping and nothing more: it carries the same SNMP
messages, with the same security, that a datagram transport would. TCP here
buys framing, reachability and the ability to tell a refused connection from a
lost packet. It is not TLS, and it is not :RFC:`6353`.
"""

import socket

from pysnmp.carrier.asyncio.stream.base import StreamAsyncioTransport
from pysnmp.carrier.base import AbstractTransportAddress

#: ``transportDomainTcpIpv4``, TRANSPORT-ADDRESS-MIB (:RFC:`3419#section-3`).
domainName = snmpTCPDomain = transportDomainTcpIpv4 = (1, 3, 6, 1, 2, 1, 100, 1, 5)


class TcpTransportAddress(tuple, AbstractTransportAddress):
    """An IPv4 endpoint, as the `(host, port)` pair `socket` uses."""

    pass


class TcpAsyncioTransport(StreamAsyncioTransport):
    """SNMP over TCP/IPv4.

    :RFC:`3430#section-3` recommends port 161 for command responders and 162
    for notification receivers, the same numbers as the datagram mapping.
    """

    sockFamily = socket.AF_INET
    addressType = TcpTransportAddress
    # Not a bind: this is what an unconnected socket has for a local address,
    # so S104 does not apply -- as in the UDP transport.
    unboundLocalAddress = ("0.0.0.0", 0)  # noqa: S104


TcpTransport = TcpAsyncioTransport
