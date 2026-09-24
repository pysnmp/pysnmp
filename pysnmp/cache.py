#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# Limited-size dictionary-like class to use for caches
#
"""A bounded mapping that evicts the least-used entries when it fills up."""


class Cache:
    """A dictionary that never grows past a fixed number of entries.

    Reads are counted. When the cache is full, the tenth of its entries with
    the fewest reads is dropped to make room, so an entry earns its place by
    being looked up rather than by being recent.
    """

    def __init__(self, maxSize=256):
        """Make a cache holding at most `maxSize` entries."""
        self.__maxSize = maxSize
        self.__size = 0
        self.__chopSize = maxSize // 10
        self.__chopSize = self.__chopSize or 1
        self.__cache = {}
        self.__usage = {}

    def __contains__(self, k):
        """Whether `k` is cached, without counting it as a read."""
        return k in self.__cache

    def __getitem__(self, k):
        """The value cached under `k`, counting the lookup against eviction."""
        self.__usage[k] += 1
        return self.__cache[k]

    def __len__(self):
        """How many entries are cached."""
        return self.__size

    def __setitem__(self, k, v):
        """Cache `v` under `k`, evicting the least-used entries if full."""
        if self.__size >= self.__maxSize:
            usageKeys = sorted(self.__usage, key=lambda x, d=self.__usage: d[x])
            for _k in usageKeys[: self.__chopSize]:
                del self.__cache[_k]
                del self.__usage[_k]
            self.__size -= self.__chopSize
        if k not in self.__cache:
            self.__size += 1
            self.__usage[k] = 0
        self.__cache[k] = v

    def __delitem__(self, k):
        """Drop `k` and forget how often it was read."""
        del self.__cache[k]
        del self.__usage[k]
        self.__size -= 1
