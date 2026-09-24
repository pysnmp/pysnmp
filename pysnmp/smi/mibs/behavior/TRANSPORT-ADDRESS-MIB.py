# RFC 3419 section 3: TransportAddressIPv4 is four address octets then two port
# octets, TransportAddressIPv6 sixteen then two, both network byte order. The
# lengths are in the module; the socket-address form is not. As with
# SNMPv2-TM's SnmpUDPAddress, a value doubles as the (host, port) tuple Python
# socket calls take, and for IPv6 as the four-element form with flow info and
# scope id, which is a property of the transport rather than of the MIB.

import socket as _socket

from pysnmp import error as _pysnmp_error

_TC = TextualConvention

_HAS_IPV6 = _socket.has_ipv6


def _packed(family, value):
    return (
        _socket.inet_pton(family, value[0])
        + bytes(((value[1] >> 8) & 0xFF,))
        + bytes((value[1] & 0xFF,))
    )


def _prettyInIPv4(self, value):
    if isinstance(value, tuple):
        value = _packed(_socket.AF_INET, value)

    return _TC.prettyIn(self, value)


def _asSocketAddressIPv4(self):
    if not hasattr(self, "_socket_address"):
        octets = self.asOctets()
        self._socket_address = (
            _socket.inet_ntop(_socket.AF_INET, octets[:4]),
            octets[4] << 8 | octets[5],
        )

    return self._socket_address


def _prettyInIPv6(self, value):
    if not _HAS_IPV6:
        raise _pysnmp_error.PySnmpError("IPv6 not supported by platform")

    if isinstance(value, tuple):
        value = _packed(_socket.AF_INET6, value)

    return _TC.prettyIn(self, value)


def _asSocketAddressIPv6(self):
    if not hasattr(self, "_socket_address"):
        if not _HAS_IPV6:
            raise _pysnmp_error.PySnmpError("IPv6 not supported by platform")

        octets = self.asOctets()
        self._socket_address = (
            _socket.inet_ntop(_socket.AF_INET6, octets[:16]),
            octets[16] << 8 | octets[17],
            0,  # flow info
            0,  # scope id
        )

    return self._socket_address


TransportAddressIPv4.prettyIn = _prettyInIPv4
TransportAddressIPv4.__iter__ = lambda self: iter(_asSocketAddressIPv4(self))
TransportAddressIPv4.__getitem__ = lambda self, item: _asSocketAddressIPv4(self)[item]

TransportAddressIPv6.prettyIn = _prettyInIPv6
TransportAddressIPv6.__iter__ = lambda self: iter(_asSocketAddressIPv6(self))
TransportAddressIPv6.__getitem__ = lambda self, item: _asSocketAddressIPv6(self)[item]
