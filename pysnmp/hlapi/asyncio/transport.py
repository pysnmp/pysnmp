#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""Where to send a request: UDP, TCP, their IPv6 forms, and Unix domain targets.

A target pairs a transport with an address, and resolves a hostname to one
before the engine needs it.
"""

import socket
from typing import cast

from pysnmp.carrier.asyncio.dgram import udp, udp6, unix
from pysnmp.carrier.asyncio.stream import tcp, tcp6
from pysnmp.error import PySnmpError
from pysnmp.hlapi.transport import AbstractTransportTarget

__all__ = [
    "Tcp6TransportTarget",
    "TcpTransportTarget",
    "Udp6TransportTarget",
    "UdpTransportTarget",
    "UnixTransportTarget",
]


class UdpTransportTarget(AbstractTransportTarget[tuple[str, int]]):
    """Creates UDP/IPv4 configuration entry and initialize socket API if needed.

    This object can be used for adding new entries to Local Configuration
    Datastore (LCD) managed by :py:class:`~pysnmp.hlapi.SnmpEngine`
    class instance.

    See :RFC:`1906#section-3` for more information on the UDP transport mapping.

    Parameters
    ----------
    transportAddr : tuple
        Indicates remote address in Python :py:mod:`socket` module format
        which is a tuple of FQDN, port where FQDN is a string representing
        either hostname or IPv4 address in quad-dotted form, port is an
        integer.
    timeout : int
        Response timeout in seconds.
    retries : int
        Maximum number of request retries, 0 retries means just a single
        request.
    tagList : str
        Arbitrary string that contains a list of tag values which are used
        to select target addresses for a particular operation
        (:RFC:`3413#section-4.1.4`).


    Notes
    -----
    Resolving `transportAddr` calls `socket.getaddrinfo`, which blocks. Built
    outside a running event loop this happens in the constructor, as it always
    has. Built *inside* one -- which is where an asyncio application builds
    things -- it is deferred instead, so a slow resolver cannot stall the loop,
    and `transportAddr` raises until something has awaited
    :py:meth:`~pysnmp.hlapi.transport.AbstractTransportTarget.resolve`.

    Every hlapi command awaits it for you, so passing a freshly built target
    straight to ``get_cmd`` and friends needs no change. Await it yourself only
    if you read the resolved address before issuing a request::

        target = await UdpTransportTarget(('example.com', 161)).resolve()
        print(target.transportAddr)

    Examples
    --------
    >>> from pysnmp.hlapi.asyncio import UdpTransportTarget
    >>> UdpTransportTarget(('127.0.0.1', 161))
    UdpTransportTarget(('127.0.0.1', 161), timeout=1, retries=5, tagList=b'')
    >>>

    """

    transportDomain = udp.domainName
    protoTransport = udp.UdpAsyncioTransport

    def _resolveAddr(self, transportAddr: tuple[str, int]) -> tuple[str, int]:
        try:
            # AF_INET pins the sockaddr to (host, port), but getaddrinfo is
            # typed over every address family it can return, so the slice has
            # to be narrowed by hand.
            return cast(
                tuple[str, int],
                socket.getaddrinfo(
                    transportAddr[0],
                    transportAddr[1],
                    socket.AF_INET,
                    socket.SOCK_DGRAM,
                    socket.IPPROTO_UDP,
                )[0][4][:2],
            )
        except socket.gaierror as e:
            raise PySnmpError(
                "Bad IPv4/UDP transport address {}: {}".format(
                    "@".join([str(x) for x in transportAddr]), e
                )
            ) from e


class Udp6TransportTarget(AbstractTransportTarget[tuple[str, int]]):
    """Creates UDP/IPv6 configuration entry and initialize socket API if needed.

    This object can be used by
    :py:func:`~pysnmp.hlapi.asyncio.get_cmd` and the other command-generator
    coroutines, or by :py:func:`~pysnmp.hlapi.asyncio.send_notification`,
    for adding new entries to Local Configuration
    Datastore (LCD) managed by :py:class:`~pysnmp.hlapi.SnmpEngine`
    class instance.

    See :RFC:`1906#section-3`, :RFC:`2851#section-4` for more information
    on the UDP and IPv6 transport mapping.

    Parameters
    ----------
    transportAddr : tuple
        Indicates remote address in Python :py:mod:`socket` module format
        which is a tuple of FQDN, port where FQDN is a string representing
        either hostname or IPv6 address in one of three conventional forms
        (:RFC:`1924#section-3`), port is an integer.
    timeout : int
        Response timeout in seconds.
    retries : int
        Maximum number of request retries, 0 retries means just a single
        request.
    tagList : str
        Arbitrary string that contains a list of tag values which are used
        to select target addresses for a particular operation
        (:RFC:`3413#section-4.1.4`).


    Notes
    -----
    Built inside a running event loop, address resolution is deferred so that a
    slow resolver cannot stall it; every hlapi command awaits it for you. See
    :py:class:`~pysnmp.hlapi.asyncio.UdpTransportTarget` for the detail, and
    :py:meth:`~pysnmp.hlapi.transport.AbstractTransportTarget.resolve` to await
    it yourself.

    Examples
    --------
    A link-local address keeps its scope, in the ``%`` form :RFC:`4007#section-11`
    defines, since such an address means nothing without one.

    >>> from pysnmp.hlapi.asyncio import Udp6TransportTarget
    >>> Udp6TransportTarget(('::1', 161))
    Udp6TransportTarget(('::1', 161), timeout=1, retries=5, tagList=b'')
    >>> Udp6TransportTarget(('FEDC:BA98:7654:3210:FEDC:BA98:7654:3210', 161))
    Udp6TransportTarget(('fedc:ba98:7654:3210:fedc:ba98:7654:3210', 161), timeout=1, retries=5, tagList=b'')
    >>> Udp6TransportTarget(('1080:0:0:0:8:800:200C:417A', 161))
    Udp6TransportTarget(('1080::8:800:200c:417a', 161), timeout=1, retries=5, tagList=b'')
    >>> Udp6TransportTarget(('::0', 161))
    Udp6TransportTarget(('::', 161), timeout=1, retries=5, tagList=b'')
    >>> Udp6TransportTarget(('::', 161))
    Udp6TransportTarget(('::', 161), timeout=1, retries=5, tagList=b'')
    >>>

    """

    transportDomain = udp6.domainName
    protoTransport = udp6.Udp6AsyncioTransport

    def _resolveAddr(self, transportAddr: tuple[str, int]) -> tuple[str, int]:
        try:
            # An AF_INET6 sockaddr is (host, port, flowinfo, scopeid).
            # getaddrinfo() resolves a zone for us -- 'fe80::1%eth0' comes back
            # as ('fe80::1', 161, 0, 7) -- and that scope ID is how the kernel
            # picks the outgoing interface for a link-local destination.
            # Truncating to (host, port) threw it away before it could reach
            # sendto(), which made link-local addresses unusable.
            # AF_INET6 pins the sockaddr to four parts, but getaddrinfo is
            # typed over every address family it can return, so the shape has
            # to be narrowed by hand -- as in UdpTransportTarget above.
            host, port, _, scopeId = cast(
                tuple[str, int, int, int],
                socket.getaddrinfo(
                    transportAddr[0],
                    transportAddr[1],
                    socket.AF_INET6,
                    socket.SOCK_DGRAM,
                    socket.IPPROTO_UDP,
                )[0][4],
            )

        except socket.gaierror as e:
            raise PySnmpError(
                "Bad IPv6/UDP transport address {}: {}".format(
                    "@".join([str(x) for x in transportAddr]), e
                )
            ) from e

        # The scope rides in the host string, in the RFC 4007 section 11 form
        # that produced it, rather than widening this tuple: the transport
        # resolves it back to a sockaddr scope ID in normalizeAddress(). That
        # keeps a target's address the (host, port) pair every other transport
        # uses, and keeps the numeric zone -- which is what getaddrinfo gives
        # us -- rather than the interface name, which may not survive a trip
        # through the target address table.
        return (f"{host}%{scopeId}" if scopeId else host, port)


class TcpTransportTarget(AbstractTransportTarget[tuple[str, int]]):
    """Creates TCP/IPv4 configuration entry and initialize socket API if needed.

    This object can be used for adding new entries to Local Configuration
    Datastore (LCD) managed by :py:class:`~pysnmp.hlapi.SnmpEngine`
    class instance.

    See :RFC:`3430` for more information on the TCP transport mapping.

    TCP is worth reaching for in three situations. A response too large for the
    path MTU arrives instead of being fragmented or dropped, which is what the
    `tooBig` retry loop on a wide table is really about. A connection crosses a
    stateful NAT or a filtered path where a return datagram would not. And a
    refused connection is reported as such, so an application can tell a device
    that declined to answer from one it could not reach -- a distinction UDP
    cannot make, and the reason a failed poll over UDP can look like a device
    fault when it is not.

    :RFC:`3430` is a transport mapping only and implies no security of its own:
    the same SNMP messages travel it, protected by whatever USM or community
    the caller configured, and nothing more. It is not TLS.

    Parameters
    ----------
    transportAddr : tuple
        Indicates remote address in Python :py:mod:`socket` module format
        which is a tuple of FQDN, port where FQDN is a string representing
        either hostname or IPv4 address in quad-dotted form, port is an
        integer. :RFC:`3430#section-3` recommends port 161 for command
        responders and 162 for notification receivers.
    timeout : int
        Response timeout in seconds.
    retries : int
        Maximum number of request retries, 0 retries means just a single
        request.
    tagList : str
        Arbitrary string that contains a list of tag values which are used
        to select target addresses for a particular operation
        (:RFC:`3413#section-4.1.4`).


    Notes
    -----
    Built inside a running event loop, address resolution is deferred so that a
    slow resolver cannot stall it; every hlapi command awaits it for you. See
    :py:class:`~pysnmp.hlapi.asyncio.UdpTransportTarget` for the detail, and
    :py:meth:`~pysnmp.hlapi.transport.AbstractTransportTarget.resolve` to await
    it yourself.

    Examples
    --------
    >>> from pysnmp.hlapi.asyncio import TcpTransportTarget
    >>> TcpTransportTarget(('127.0.0.1', 161))
    TcpTransportTarget(('127.0.0.1', 161), timeout=1, retries=5, tagList=b'')
    >>>

    """

    transportDomain = tcp.domainName
    protoTransport = tcp.TcpAsyncioTransport

    def _resolveAddr(self, transportAddr: tuple[str, int]) -> tuple[str, int]:
        try:
            # AF_INET pins the sockaddr to (host, port); the cast narrows what
            # getaddrinfo is typed to return, as in UdpTransportTarget.
            return cast(
                tuple[str, int],
                socket.getaddrinfo(
                    transportAddr[0],
                    transportAddr[1],
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                )[0][4][:2],
            )
        except socket.gaierror as e:
            raise PySnmpError(
                "Bad IPv4/TCP transport address {}: {}".format(
                    "@".join([str(x) for x in transportAddr]), e
                )
            ) from e


class Tcp6TransportTarget(AbstractTransportTarget[tuple[str, int]]):
    """Creates TCP/IPv6 configuration entry and initialize socket API if needed.

    The IPv6 form of :py:class:`~pysnmp.hlapi.asyncio.TcpTransportTarget`; see
    there for what the TCP mapping (:RFC:`3430`) is for.

    Parameters
    ----------
    transportAddr : tuple
        Indicates remote address in Python :py:mod:`socket` module format
        which is a tuple of FQDN, port where FQDN is a string representing
        either hostname or IPv6 address in one of three conventional forms
        (:RFC:`1924#section-3`), port is an integer.
    timeout : int
        Response timeout in seconds.
    retries : int
        Maximum number of request retries, 0 retries means just a single
        request.
    tagList : str
        Arbitrary string that contains a list of tag values which are used
        to select target addresses for a particular operation
        (:RFC:`3413#section-4.1.4`).


    Examples
    --------
    A link-local address keeps its scope, in the ``%`` form :RFC:`4007#section-11`
    defines, since such an address means nothing without one.

    >>> from pysnmp.hlapi.asyncio import Tcp6TransportTarget
    >>> Tcp6TransportTarget(('::1', 161))
    Tcp6TransportTarget(('::1', 161), timeout=1, retries=5, tagList=b'')
    >>>

    """

    transportDomain = tcp6.domainName
    protoTransport = tcp6.Tcp6AsyncioTransport

    def _resolveAddr(self, transportAddr: tuple[str, int]) -> tuple[str, int]:
        try:
            # An AF_INET6 sockaddr is (host, port, flowinfo, scopeid).
            host, port, _, scopeId = cast(
                tuple[str, int, int, int],
                socket.getaddrinfo(
                    transportAddr[0],
                    transportAddr[1],
                    socket.AF_INET6,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                )[0][4],
            )

        except socket.gaierror as e:
            raise PySnmpError(
                "Bad IPv6/TCP transport address {}: {}".format(
                    "@".join([str(x) for x in transportAddr]), e
                )
            ) from e

        # The scope rides in the host string, as it does for UDP/IPv6 -- but
        # here it stays there: `create_connection` resolves the zone itself,
        # where `sendto` needs it already turned into a sockaddr scope ID.
        return (f"{host}%{scopeId}" if scopeId else host, port)


class UnixTransportTarget(AbstractTransportTarget[str]):
    """A Unix domain socket to send to, named by its filesystem path.

    A path is not looked up anywhere, so unlike the IP transports there is
    nothing here that could stall an event loop, and resolution is never
    deferred: a bad path is rejected by the constructor in every context.
    """

    #: Resolving a path only checks its type -- see the class docstring.
    resolutionBlocks = False

    transportDomain = unix.domainName
    protoTransport = unix.UnixAsyncioTransport

    def _resolveAddr(self, transportAddr: str) -> str:
        if not isinstance(transportAddr, str):
            raise PySnmpError(
                f"Bad Unix-domain transport address {transportAddr!r}: expected a path string"
            )
        return transportAddr
