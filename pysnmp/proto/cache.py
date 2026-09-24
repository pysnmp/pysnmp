#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The dispatcher's record of requests it has sent and not yet answered."""

from pysnmp.proto import error


class Cache:
    """Holds a request until its response arrives, or until it expires.

    Keyed by a handle the dispatcher hands out; `expire` is what the timer calls
    to sweep the requests nothing ever answered.
    """

    def __init__(self):
        """Nothing is cached until a request is added."""
        self.__cacheRepository = {}

    def add(self, index, **kwargs):
        """Remember a request under a handle, returning the handle back."""
        self.__cacheRepository[index] = kwargs
        return index

    def pop(self, index):
        """Take a request back out, removing it. `None` where the handle is unknown.

        A late response and a second response to the same request look identical here,
        and both get `None` rather than an error -- neither is worth failing over.
        """
        if index in self.__cacheRepository:
            cachedParams = self.__cacheRepository[index]
        else:
            return
        del self.__cacheRepository[index]
        return cachedParams

    def update(self, index, **kwargs):
        """Add to what is remembered for a request, which must already be there."""
        if index not in self.__cacheRepository:
            raise error.ProtocolError(f"Cache miss on update for {kwargs}")
        self.__cacheRepository[index].update(kwargs)

    def expire(self, cbFun, cbCtx):
        """Sweep requests the callback says are past due.

        The callback decides, not a fixed age, because what counts as expired differs
        by message processing model. Called with no callback this does nothing.
        """
        for index, cachedParams in list(self.__cacheRepository.items()):
            if cbFun:
                if cbFun(index, cachedParams, cbCtx):
                    if index in self.__cacheRepository:
                        del self.__cacheRepository[index]
