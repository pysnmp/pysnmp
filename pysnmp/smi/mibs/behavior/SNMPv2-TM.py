# RFC 3417 section 3: an SnmpUDPAddress is six octets, IPv4 address then UDP
# port, both network byte order. That much the SIZE constraint and DISPLAY-HINT
# already carry. What is written here is the other direction pysnmp needs -- the
# value doubling as a Python socket address, the (host, port) tuple socket calls
# take and return -- which is a property of the transport it names rather than
# anything the module says.

from socket import AF_INET as _AF_INET
from socket import inet_ntop as _inet_ntop
from socket import inet_pton as _inet_pton

_TC = TextualConvention


def _prettyIn(self, value):
    if isinstance(value, tuple):
        # A Python socket address, the counterpart of _asSocketAddress below.
        # Address-family specific, so it is handled here; everything else, the
        # DISPLAY-HINT text form included, belongs to TextualConvention.
        value = (
            _inet_pton(_AF_INET, value[0])
            + bytes(((value[1] >> 8) & 0xFF,))
            + bytes((value[1] & 0xFF,))
        )

    return _TC.prettyIn(self, value)


def _asSocketAddress(self):
    if not hasattr(self, "_socket_address"):
        octets = self.asOctets()
        self._socket_address = (
            _inet_ntop(_AF_INET, octets[:4]),
            octets[4] << 8 | octets[5],
        )

    return self._socket_address


SnmpUDPAddress.prettyIn = _prettyIn
SnmpUDPAddress.__iter__ = lambda self: iter(_asSocketAddress(self))
SnmpUDPAddress.__getitem__ = lambda self, item: _asSocketAddress(self)[item]
