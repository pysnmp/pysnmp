#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""State a security model keeps between a request and its response."""

from pysnmp import nextid
from pysnmp.proto import error


class Cache:
    """Holds what a security model needs when the response arrives."""

    __stateReference = nextid.Integer(0xFFFFFF)

    def __init__(self):
        self.__cacheEntries = {}

    def push(self, **securityData):
        stateReference = self.__stateReference()
        self.__cacheEntries[stateReference] = securityData
        return stateReference

    def pop(self, stateReference):
        if stateReference in self.__cacheEntries:
            securityData = self.__cacheEntries[stateReference]
        else:
            raise error.ProtocolError(
                f"Cache miss for stateReference={stateReference} at {self}"
            )
        del self.__cacheEntries[stateReference]
        return securityData
