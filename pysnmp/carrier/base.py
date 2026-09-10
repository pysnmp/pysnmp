#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""What a transport and a transport dispatcher have to provide.

A dispatcher owns the event loop, routes an inbound message to whoever
registered for that transport domain, and runs timer callbacks. A transport
moves bytes for one domain. Nothing here is asyncio-specific.
"""

import functools

from pysnmp.carrier import error


@functools.total_ordering
class TimerCallable:
    """A callback the dispatcher invokes on a fixed interval.

    Compares equal to the bare function it wraps, so a caller can unregister the
    callback it registered without holding on to the wrapper.
    """

    def __init__(self, cbFun, callInterval):
        """The first call is due immediately; the interval applies from then on."""
        self.__cbFun = cbFun
        self.__nextCall = 0

        self.__callInterval = callInterval

    def __call__(self, timeNow):
        """Run the callback if its interval has elapsed, otherwise do nothing.

        The dispatcher calls every timer on every tick and each one decides for itself
        whether it is due, which is what lets callbacks on different intervals share a
        single tick.
        """
        if self.__nextCall <= timeNow:
            self.__cbFun(timeNow)
            self.__nextCall = timeNow + self.interval

    def __eq__(self, cbFun):
        """Compare equal to the bare function, so it can be unregistered by function."""
        return self.__cbFun == cbFun

    def __lt__(self, cbFun):
        """Order by the wrapped function, for `total_ordering`."""
        return self.__cbFun < cbFun

    @property
    def interval(self):
        """Seconds between calls."""
        return self.__callInterval

    @interval.setter
    def interval(self, callInterval):
        self.__callInterval = callInterval


class AbstractTransportDispatcher:
    """Owns the transports and drives the I/O loop they run on.

    Transports are registered against a transport domain, and an incoming message
    is routed to the callback registered for whichever recipient the routing
    function names. Jobs count what is still outstanding: the loop runs until
    every job has released itself, which is what stops a dispatcher from exiting
    while a request is still in flight.
    """

    def __init__(self):
        """The timer resolution is what the whole timeout mechanism is built on.

        It defaults to half a second, and the delta is the slack allowed around a tick
        so a callback due fractionally early is not deferred a whole tick.
        """
        self.__transports = {}
        self.__transportDomainMap = {}
        self.__jobs = {}
        self.__recvCallables = {}
        self.__timerCallables = []
        self.__ticks = 0
        self.__timerResolution = 0.5
        self.__timerDelta = self.__timerResolution * 0.05
        self.__nextTime = 0
        self.__routingCbFun = None

    def _cbFun(self, incomingTransport, transportAddress, incomingMessage):
        """Route one inbound message to whoever registered for it.

        The routing function names a recipient; with none registered the message goes
        to the default callback. A message that matches nothing raises rather than
        being dropped quietly, since that is a configuration mistake and losing traffic
        over it would be hard to notice.
        """
        if incomingTransport in self.__transportDomainMap:
            transportDomain = self.__transportDomainMap[incomingTransport]
        else:
            raise error.CarrierError(f"Unregistered transport {incomingTransport}")

        if self.__routingCbFun:
            recvId = self.__routingCbFun(
                transportDomain, transportAddress, incomingMessage
            )
        else:
            recvId = None

        if recvId in self.__recvCallables:
            self.__recvCallables[recvId](
                self, transportDomain, transportAddress, incomingMessage
            )
        else:
            raise error.CarrierError(
                f'No callback for "{recvId!r}" found - loosing incoming event'
            )

    # Dispatcher API

    def registerRoutingCbFun(self, routingCbFun):
        """Set the function that decides which receiver an inbound message belongs to."""
        if self.__routingCbFun:
            raise error.CarrierError("Data routing callback already registered")
        self.__routingCbFun = routingCbFun

    def unregisterRoutingCbFun(self):
        """Drop the routing function, sending everything to the default receiver."""
        if self.__routingCbFun:
            self.__routingCbFun = None

    def registerRecvCbFun(self, recvCb, recvId=None):
        """Register a receiver, `recvId` being `None` for the default one."""
        if recvId in self.__recvCallables:
            raise error.CarrierError(
                "Receive callback {!r} already registered".format(
                    recvId is None and "<default>" or recvId
                )
            )
        self.__recvCallables[recvId] = recvCb

    def unregisterRecvCbFun(self, recvId=None):
        """Drop a receiver. Unknown ids are ignored."""
        if recvId in self.__recvCallables:
            del self.__recvCallables[recvId]

    def registerTimerCbFun(self, timerCbFun, tickInterval=None):
        """Register a periodic callback, defaulting to the dispatcher's own resolution."""
        if not tickInterval:
            tickInterval = self.__timerResolution
        self.__timerCallables.append(TimerCallable(timerCbFun, tickInterval))

    def unregisterTimerCbFun(self, timerCbFun=None):
        """Drop one timer callback, or all of them when given none."""
        if timerCbFun:
            self.__timerCallables.remove(timerCbFun)
        else:
            self.__timerCallables = []

    def registerTransport(self, tDomain, transport):
        """Take ownership of a transport for one domain and wire its receive callback."""
        if tDomain in self.__transports:
            raise error.CarrierError(f"Transport {tDomain} already registered")
        transport.registerCbFun(self._cbFun)
        self.__transports[tDomain] = transport
        self.__transportDomainMap[transport] = tDomain

    def unregisterTransport(self, tDomain):
        """Release a transport, leaving it open. Closing it is the caller's to do."""
        if tDomain not in self.__transports:
            raise error.CarrierError(f"Transport {tDomain} not registered")
        self.__transports[tDomain].unregisterCbFun()
        del self.__transportDomainMap[self.__transports[tDomain]]
        del self.__transports[tDomain]

    def getTransport(self, transportDomain):
        """The transport registered for a domain. Raises where there is none."""
        if transportDomain in self.__transports:
            return self.__transports[transportDomain]
        raise error.CarrierError(f"Transport {transportDomain} not registered")

    def sendMessage(self, outgoingMessage, transportDomain, transportAddress):
        """Hand a message to the transport for its domain."""
        if transportDomain in self.__transports:
            self.__transports[transportDomain].sendMessage(
                outgoingMessage, transportAddress
            )
        else:
            raise error.CarrierError(
                f"No suitable transport domain for {transportDomain}"
            )

    def getTimerResolution(self):
        """Seconds between timer ticks."""
        return self.__timerResolution

    def setTimerResolution(self, timerResolution):
        """Change the tick interval, moving callbacks that were on the old default.

        A callback registered without an interval of its own took the resolution in
        force at the time; those follow the new value, while one that named an interval
        keeps it. Values outside 10ms to 10s are refused as unworkable.
        """
        if timerResolution < 0.01 or timerResolution > 10:
            raise error.CarrierError("Impossible timer resolution")

        for timerCallable in self.__timerCallables:
            if timerCallable.interval == self.__timerResolution:
                # Update periodics for default resolutions
                timerCallable.interval = timerResolution

        self.__timerResolution = timerResolution
        self.__timerDelta = timerResolution * 0.05

    def getTimerTicks(self):
        """Ticks since the dispatcher started, which is what timeouts are counted in."""
        return self.__ticks

    def handleTimerTick(self, timeNow):
        """Advance the tick count and run whichever timer callbacks are due.

        A tick fires slightly before the resolution has fully elapsed -- the delta --
        so a callback due fractionally early is not held back a whole tick.
        """
        if self.__nextTime == 0:  # initial initialization
            self.__nextTime = timeNow + self.__timerResolution - self.__timerDelta

        if self.__nextTime >= timeNow:
            return

        self.__ticks += 1
        self.__nextTime = timeNow + self.__timerResolution - self.__timerDelta

        for timerCallable in self.__timerCallables:
            timerCallable(timeNow)

    def jobStarted(self, jobId, count=1):
        """Record outstanding work, which keeps the loop from exiting under it."""
        if jobId in self.__jobs:
            self.__jobs[jobId] += count
        else:
            self.__jobs[jobId] = count

    def jobFinished(self, jobId, count=1):
        """Retire outstanding work; the loop may exit once nothing is left."""
        self.__jobs[jobId] -= count
        if self.__jobs[jobId] == 0:
            del self.__jobs[jobId]

    def jobsArePending(self):
        """Whether anything is still outstanding."""
        return bool(self.__jobs)

    def runDispatcher(self, timeout=0.0):
        """Run the I/O loop. Concrete dispatchers implement this."""
        raise error.CarrierError("Method not implemented")

    def closeDispatcher(self):
        """Close every transport and drop every callback."""
        for tDomain in list(self.__transports):
            self.__transports[tDomain].closeTransport()
            self.unregisterTransport(tDomain)
        self.__transports.clear()
        self.unregisterRecvCbFun()
        self.unregisterTimerCbFun()


class AbstractTransportAddress:
    """An endpoint address, remembering which local address it was seen on.

    The local address is what `sockmsg` recovers for a socket bound to a wildcard,
    and it rides along on the address so a reply leaves by the interface the
    request arrived on.
    """

    _localAddress = None

    def setLocalAddress(self, s):
        """Note which local address this was seen on, and return self for chaining."""
        self._localAddress = s
        return self

    def getLocalAddress(self):
        """The local address this was seen on, or `None`."""
        return self._localAddress

    def clone(self, localAddress=None):
        """Copy the address, carrying the local address across unless one is given."""
        return self.__class__(self).setLocalAddress(
            localAddress is None and self.getLocalAddress() or localAddress
        )


class AbstractTransport:
    """One transport: a socket, opened either as a client or as a server.

    A transport names the dispatcher it was written against, since the two share
    an I/O model and pairing a transport with the wrong dispatcher would not work.
    """

    #: Dispatcher this transport was written against; isCompatibleWithDispatcher()
    #: below checks candidates against it, and every concrete transport names one.
    protoTransportDispatcher: type[AbstractTransportDispatcher] | None = None
    addressType = AbstractTransportAddress
    _cbFun = None

    @classmethod
    def isCompatibleWithDispatcher(cls, transportDispatcher):
        """Whether this transport can run on that dispatcher.

        The two share an I/O model, so a transport written against one dispatcher will
        not work under another.
        """
        return isinstance(transportDispatcher, cls.protoTransportDispatcher)

    def registerCbFun(self, cbFun):
        """Set the callback inbound messages go to. Only one transport may hold it."""
        if self._cbFun:
            raise error.CarrierError(
                f"Callback function {self._cbFun} already registered at {self}"
            )
        self._cbFun = cbFun

    def unregisterCbFun(self):
        """Drop the receive callback."""
        self._cbFun = None

    def closeTransport(self):
        """Stop delivering inbound messages. Subclasses close the socket too."""
        self.unregisterCbFun()

    # Public API

    def openClientMode(self, iface=None):
        """Open for sending. Concrete transports implement this."""
        raise error.CarrierError("Method not implemented")

    def openServerMode(self, iface):
        """Bind for receiving. Concrete transports implement this."""
        raise error.CarrierError("Method not implemented")

    def sendMessage(self, outgoingMessage, transportAddress):
        """Send one message. Concrete transports implement this."""
        raise error.CarrierError("Method not implemented")
