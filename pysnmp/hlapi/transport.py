#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""What a transport target has to provide, independent of address family."""

import asyncio
from typing import Any, Generic, TypeVar

from pysnmp import error
from pysnmp.carrier.base import AbstractTransport

__all__ = []

#: The address shape a concrete target speaks. Each transport has its own --
#: (host, port) for UDP over IPv4 and IPv6, a path string for Unix domain
#: sockets -- so the base cannot name one and have the subclasses honour it.
TransportAddrT = TypeVar("TransportAddrT")


class AbstractTransportTarget(Generic[TransportAddrT]):
    transportDomain: Any = None
    protoTransport: Any = AbstractTransport

    #: Whether `_resolveAddr` can block long enough to matter, which for the
    #: IP transports means a DNS lookup. Only those defer; a transport that
    #: merely validates what it was given resolves in the constructor whatever
    #: the context, so that a bad address is still rejected from the
    #: constructor rather than from a later `resolve`.
    resolutionBlocks: bool = True

    def __init__(
        self,
        transportAddr: TransportAddrT,
        timeout: int = 1,
        retries: int = 5,
        tagList: Any = b"",
    ) -> None:
        self._unresolvedTransportAddr = transportAddr
        self._resolvedTransportAddr: TransportAddrT | None = None
        self._resolveLock: asyncio.Lock | None = None
        self.timeout = timeout
        self.retries = retries
        self.tagList = tagList
        self.iface: tuple[str, ...] | None = None
        self.transport: Any = None

        # Resolving means getaddrinfo(), which is a blocking libc call. With no
        # loop running there is nothing to block, so do it now and behave
        # exactly as this always has: the address is ready when the constructor
        # returns, which is what every synchronous caller expects.
        #
        # Inside a running loop it is deferred instead -- see `resolve`. A
        # constructor cannot await, and there is no way to get a value back
        # into one without blocking the thread that has to produce it, so
        # deferring is the only way not to stall the loop.
        if not self.resolutionBlocks or not self._inRunningLoop():
            self._resolvedTransportAddr = self._resolveAddr(transportAddr)

    @staticmethod
    def _inRunningLoop() -> bool:
        """Whether a loop is running on this thread, and would therefore stall."""
        try:
            asyncio.get_running_loop()

        except RuntimeError:
            return False

        return True

    @property
    def transportAddr(self) -> TransportAddrT:
        """The resolved address.

        Raises `PySnmpError` if this target was built inside a running event
        loop and nothing has awaited `resolve` yet. Every hlapi entry point
        awaits it before reading this, so reaching the error means a target
        went somewhere that does not -- a synchronous code path, most likely --
        and the fix is to await `resolve` before handing it over.
        """
        if self._resolvedTransportAddr is None:
            raise error.PySnmpError(
                f"Transport address {self._unresolvedTransportAddr!r} is not "
                f"resolved yet: this target was created inside a running event "
                f"loop, so resolution was deferred to keep the loop moving. "
                f"Await {self.__class__.__name__}.resolve() before using it."
            )

        return self._resolvedTransportAddr

    @property
    def isResolved(self) -> bool:
        """Whether the address has been resolved, so reading it will not raise."""
        return self._resolvedTransportAddr is not None

    async def resolve(self) -> "AbstractTransportTarget[TransportAddrT]":
        """Resolve the address, off the event loop, if that has not happened yet.

        A no-op for a target built outside a running loop, which resolved in its
        constructor. Otherwise the lookup runs in the default executor, so the
        loop keeps serving everything else while it is outstanding.

        Safe to await more than once and from concurrent tasks: the first one
        through does the lookup and the rest wait on it, so a target shared by a
        fan-out of requests is resolved once rather than once per request.

        Returns
        -------
            self, so it can be awaited inline where the target is built.
        """
        if self._resolvedTransportAddr is not None:
            return self

        # Created here rather than in __init__ so that a target built outside a
        # loop never makes one. Nothing awaits between the test and the
        # assignment, so no other task can interleave and make a second.
        if self._resolveLock is None:
            self._resolveLock = asyncio.Lock()

        async with self._resolveLock:
            if self._resolvedTransportAddr is None:
                loop = asyncio.get_running_loop()
                self._resolvedTransportAddr = await loop.run_in_executor(
                    None, self._resolveAddr, self._unresolvedTransportAddr
                )

        return self

    def __repr__(self) -> str:
        # Never the raising property: repr() is most often reached while
        # rendering something for a human to read, a traceback included.
        addr = (
            self._resolvedTransportAddr
            if self._resolvedTransportAddr is not None
            else self._unresolvedTransportAddr
        )
        return f"{self.__class__.__name__}({addr!r}, timeout={self.timeout!r}, retries={self.retries!r}, tagList={self.tagList!r})"

    def getTransportInfo(self) -> tuple[Any, TransportAddrT]:
        return self.transportDomain, self.transportAddr

    def setLocalAddress(
        self, iface: tuple[str, ...] | None
    ) -> "AbstractTransportTarget[TransportAddrT]":
        """Set source address.

        Parameters
        ----------
        iface : tuple
            Indicates network address of a local interface from which SNMP packets will be originated.
            Format is the same as of `transportAddress`.

        Returns
        -------
            self

        """
        self.iface = iface
        return self

    def openClientMode(self) -> Any:
        self.transport = self.protoTransport().openClientMode(self.iface)
        return self.transport

    def verifyDispatcherCompatibility(self, snmpEngine: Any) -> None:
        if not self.protoTransport.isCompatibleWithDispatcher(
            snmpEngine.transportDispatcher
        ):
            raise error.PySnmpError(
                f"Transport {self.protoTransport!r} is not compatible with dispatcher {snmpEngine.transportDispatcher!r}"
            )

    def _resolveAddr(self, transportAddr: TransportAddrT) -> TransportAddrT:
        raise NotImplementedError
