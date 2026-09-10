#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# The following routines act like sendto()/recvfrom() calls but additionally
# support local address retrieval (what can be useful when listening on
# 0.0.0.0 or [::]) and source address spoofing (for transparent proxying).
#
# These routines are based on POSIX sendmsg()/recvmsg() calls which were made
# available since Python 3.3. Therefore this module is only Python 3.x
# compatible.
#
# Parts of the code below is taken from:
# http://carnivore.it/2012/10/12/python3.3_sendmsg_and_recvmsg
#
"""`sendto`/`recvfrom` that also carry the local address.

Built on POSIX `sendmsg()`/`recvmsg()`. Two things the plain calls cannot do:
report which local address a datagram actually arrived on, which matters when
listening on 0.0.0.0 or [::], and set the source address on the way out, which
is what transparent proxying needs.
"""

import ctypes
import ipaddress
import socket

from pysnmp import debug

uint32_t = ctypes.c_uint32
in_addr_t = uint32_t


class in_addr(ctypes.Structure):
    """The C `struct in_addr`: one IPv4 address."""

    _fields_ = [("s_addr", in_addr_t)]


class in6_addr_U(ctypes.Union):
    """The union inside `struct in6_addr`, viewing the address at three widths."""

    _fields_ = [
        ("__u6_addr8", ctypes.c_uint8 * 16),
        ("__u6_addr16", ctypes.c_uint16 * 8),
        ("__u6_addr32", ctypes.c_uint32 * 4),
    ]


class in6_addr(ctypes.Structure):
    """The C `struct in6_addr`: one IPv6 address."""

    _fields_ = [
        ("__in6_u", in6_addr_U),
    ]


class in_pktinfo(ctypes.Structure):
    """The C `struct in_pktinfo`: which interface and local address a datagram used."""

    _fields_ = [
        ("ipi_ifindex", ctypes.c_int),
        ("ipi_spec_dst", in_addr),
        ("ipi_addr", in_addr),
    ]


class in6_pktinfo(ctypes.Structure):
    """The C `struct in6_pktinfo`: the IPv6 form of `in_pktinfo`."""

    _fields_ = [
        ("ipi6_addr", in6_addr),
        ("ipi6_ifindex", ctypes.c_uint),
    ]


def getRecvFrom(addressType):

    def recvfrom(s, sz):
        _to = None

        data, ancdata, msg_flags, _from = s.recvmsg(sz, socket.CMSG_LEN(sz))

        for anc in ancdata:
            if anc[0] == socket.SOL_IP and anc[1] == socket.IP_PKTINFO:
                addr = in_pktinfo.from_buffer_copy(anc[2])
                addr = ipaddress.IPv4Address(memoryview(addr.ipi_addr).tobytes())
                _to = (str(addr), s.getsockname()[1])
                break

            elif anc[0] == socket.SOL_IPV6 and anc[1] == socket.IPV6_PKTINFO:
                addr = in6_pktinfo.from_buffer_copy(anc[2])
                addr = ipaddress.ip_address(memoryview(addr.ipi6_addr).tobytes())
                _to = (str(addr), s.getsockname()[1])
                break

        debug.logger & debug.flagIO and debug.logger(
            f"recvfrom: received {len(data)} octets from {_from} to {_to}; "
            f"iov blob {ancdata!r}"
        )

        return data, addressType(_from).setLocalAddress(_to)

    return recvfrom


def getSendTo(addressType):

    def sendto(s, _data, _to):
        ancdata = []
        if type(_to) is addressType:
            addr = ipaddress.ip_address(_to.getLocalAddress()[0])

        else:
            addr = ipaddress.ip_address(s.getsockname()[0])

        if type(addr) is ipaddress.IPv4Address:
            _f = in_pktinfo()
            _f.ipi_spec_dst = in_addr.from_buffer_copy(addr.packed)
            ancdata = [(socket.SOL_IP, socket.IP_PKTINFO, memoryview(_f).tobytes())]

        elif s.family == socket.AF_INET6 and type(addr) is ipaddress.IPv6Address:
            _f = in6_pktinfo()
            _f.ipi6_addr = in6_addr.from_buffer_copy(addr.packed)
            ancdata = [(socket.SOL_IPV6, socket.IPV6_PKTINFO, memoryview(_f).tobytes())]

        debug.logger & debug.flagIO and debug.logger(
            f"sendto: sending {len(_data)} octets to {_to}; address {addr!r}; "
            f"iov blob {ancdata!r}"
        )

        return s.sendmsg([_data], ancdata, 0, _to)

    return sendto
