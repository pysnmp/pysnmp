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
        """Coerce to a four-part IPv6 address, keeping the scope and dropping flowinfo.

        The scope is not decoration. A link-local destination has no meaning without
        it -- `fe80::1` names a different host on every interface -- so the kernel
        requires a scope ID to pick the outgoing one, and `sendto()` fails with
        EINVAL without it. This method's result is what goes to `sendto()`, so
        stripping the zone here made every link-local address unusable, which is how
        you reach an unconfigured switch.

        `flowinfo` is zeroed, since that genuinely does not identify an endpoint.

        A zone may arrive as a name (`fe80::1%eth0`), which the sockaddr cannot carry:
        it is resolved to the interface index the kernel wants.
        """
        localAddress = None
        if isinstance(transportAddress, AbstractTransportAddress):
            localAddress = transportAddress.getLocalAddress()

        host, _, zone = transportAddress[0].partition("%")

        if len(transportAddress) > 3 and transportAddress[3]:
            scopeId = transportAddress[3]
        elif zone:
            scopeId = self._scopeIdOf(zone)
        else:
            scopeId = 0

        normalizedAddress = self.addressType(
            (
                host,
                transportAddress[1],
                0,  # flowinfo
                scopeId,
            )
        )
        if localAddress:
            normalizedAddress.setLocalAddress(localAddress)

        return DgramAsyncioProtocol.normalizeAddress(self, normalizedAddress)

    @staticmethod
    def _scopeIdOf(zone):
        """The interface index a zone names, or the zone itself if already numeric.

        An unknown interface name yields 0 rather than raising: that is the
        unscoped behaviour this had before, and failing to send is a better
        diagnostic from `sendto()` than a `socket` exception out of address
        normalization.
        """
        if zone.isdigit():
            return int(zone)

        try:
            return socket.if_nametoindex(zone)

        except OSError:
            return 0


Udp6Transport = Udp6AsyncioTransport
