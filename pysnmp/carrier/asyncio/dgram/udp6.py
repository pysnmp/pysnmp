#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
import socket

from pysnmp.carrier.asyncio.dgram.base import DgramAsyncioProtocol
from pysnmp.carrier.base import AbstractTransportAddress

domainName = snmpUDP6Domain = (1, 3, 6, 1, 2, 1, 100, 1, 2)


class Udp6TransportAddress(tuple, AbstractTransportAddress):
    pass


class Udp6AsyncioTransport(DgramAsyncioProtocol):
    sockFamily = socket.has_ipv6 and socket.AF_INET6 or None
    addressType = Udp6TransportAddress
    unboundLocalAddress = ("::", 0, 0, 0)

    def normalizeAddress(self, transportAddress):
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
