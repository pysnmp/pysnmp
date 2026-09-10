#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""SNMP over UDP/IPv6, transport domain 1.3.6.1.2.1.100.1.2."""

import socket

from pysnmp.carrier.asyncio.dgram.base import DgramAsyncioProtocol
from pysnmp.carrier.base import AbstractTransportAddress

domainName = snmpUDP6Domain = (1, 3, 6, 1, 2, 1, 100, 1, 2)


class Udp6TransportAddress(tuple, AbstractTransportAddress):
    """An IPv6 endpoint, as the `(host, port, flowinfo, scopeid)` tuple `socket` uses."""

    pass


class Udp6AsyncioTransport(DgramAsyncioProtocol):
    """SNMP over UDP/IPv6.

    Addresses are normalized so a scoped or IPv4-mapped form compares equal to the
    plain one it means.
    """

    sockFamily = socket.has_ipv6 and socket.AF_INET6 or None
    addressType = Udp6TransportAddress
    unboundLocalAddress = ("::", 0, 0, 0)

    def normalizeAddress(self, transportAddress):
        """Coerce to a four-part IPv6 address, dropping the zone ID and scope.

        A link-local address arrives carrying a zone (`fe80::1%eth0`) and asyncio
        reports flowinfo and scope alongside it, none of which mean anything to the
        peer. Two addresses that differ only in those parts are the same endpoint, so
        they are stripped to make addresses comparable.
        """
        localAddress = None
        if isinstance(transportAddress, AbstractTransportAddress):
            localAddress = transportAddress.getLocalAddress()

        normalizedAddress = self.addressType(
            (
                transportAddress[0].split("%")[0],  # strip zone ID
                transportAddress[1],
                0,  # flowinfo
                0,  # scopeid
            )
        )
        if localAddress:
            normalizedAddress.setLocalAddress(localAddress)

        return DgramAsyncioProtocol.normalizeAddress(self, normalizedAddress)


Udp6Transport = Udp6AsyncioTransport
