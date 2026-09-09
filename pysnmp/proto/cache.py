#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The dispatcher's record of requests it has sent and not yet answered."""

from pysnmp.proto import error


class Cache:
    def __init__(self):
        self.__cacheRepository = {}

    def add(self, index, **kwargs):
        self.__cacheRepository[index] = kwargs
        return index

    def pop(self, index):
        if index in self.__cacheRepository:
            cachedParams = self.__cacheRepository[index]
        else:
            return
        del self.__cacheRepository[index]
        return cachedParams

    def update(self, index, **kwargs):
        if index not in self.__cacheRepository:
            raise error.ProtocolError(f"Cache miss on update for {kwargs}")
        self.__cacheRepository[index].update(kwargs)

    def expire(self, cbFun, cbCtx):
        for index, cachedParams in list(self.__cacheRepository.items()):
            if cbFun:
                if cbFun(index, cachedParams, cbCtx):
                    if index in self.__cacheRepository:
                        del self.__cacheRepository[index]
