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
        self._resolveLookup: asyncio.Future[TransportAddrT] | None = None
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
        fan-out of requests is resolved once rather than once per request. That
        holds under cancellation too -- a caller that gives up leaves the lookup
        running for whoever else wants it, rather than throwing away a result
        the executor thread is going to produce anyway.

        Cancelling a caller still cancels promptly: what it awaits is a shield,
        not the lookup, so giving up on a request never means waiting on DNS.

        Returns
        -------
            self, so it can be awaited inline where the target is built.
        """
        if self._resolvedTransportAddr is not None:
            return self

        # No lock anywhere below. Picking up the lookup and, if there is none,
        # starting one happens without an await in between, so the loop cannot
        # switch tasks in the middle of it and no two callers can start one.
        # The shared future is what makes the lookup happen once; a lock would
        # add an await point and guard nothing that is not already atomic.
        lookup = self._resolveLookup

        # A lookup that finished without an answer -- it raised, or it was
        # cancelled outright -- is not something to hand the next caller:
        # keeping it would make every later resolve() re-raise the first
        # failure and never try again. Decided here, where the lookup is picked
        # up, rather than from its done callback, because the two are scheduled
        # independently and which of them runs first is not something asyncio
        # promises.
        if lookup is not None and lookup.done():
            if lookup.cancelled() or lookup.exception() is not None:
                lookup = self._resolveLookup = None

        if lookup is None:
            loop = asyncio.get_running_loop()
            lookup = self._resolveLookup = loop.run_in_executor(
                None, self._resolveAddr, self._unresolvedTransportAddr
            )
            # An executor thread that has started cannot be called off, so the
            # result arrives whether or not anyone is still waiting for it.
            # Recording it from here rather than only from the await below is
            # what makes the once-only guarantee hold when every caller has
            # been cancelled by the time it lands.
            lookup.add_done_callback(self._lookupDone)

        # Shielded so that one caller's cancellation does not cancel the lookup
        # the others are waiting on.
        self._resolvedTransportAddr = await asyncio.shield(lookup)

        return self

    def _lookupDone(self, lookup: asyncio.Future[TransportAddrT]) -> None:
        """Take the result off a finished lookup, whether or not anyone waited."""
        if lookup.cancelled() or lookup.exception() is not None:
            # Reading the exception is the point: a lookup whose callers were
            # all cancelled has nobody to raise to, and an asyncio future whose
            # exception is never retrieved is reported as an error when it is
            # collected. Discarding the failed lookup is `resolve`'s job -- see
            # there for why it cannot be done from here.
            return

        self._resolvedTransportAddr = lookup.result()

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
