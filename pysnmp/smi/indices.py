#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Dictionaries that keep their keys in order, including OID order.

GETNEXT has to find the successor of an OID, which a plain dict cannot do.
`OidOrderedDict` sorts by OID component rather than lexically, so 1.3.6.1.10
follows 1.3.6.1.9 rather than preceding it.
"""

from bisect import bisect


class OrderedDict(dict):
    """Ordered dictionary used for indices."""

    def __init__(self, *args, **kwargs):
        """Key order is tracked alongside the mapping and sorted lazily.

        The dirty flag is what makes that lazy: keys are appended on insert and the
        ordering is computed on the first read that needs it, so a load of many
        objects sorts once rather than on every insert.
        """
        self.__keys = []
        self.__dirty = True
        super().__init__()
        if args:
            self.update(*args)
        if kwargs:
            self.update(**kwargs)

    def __setitem__(self, key, value):
        if key not in self:
            self.__keys.append(key)
            self.__dirty = True
        super().__setitem__(key, value)

    def __delitem__(self, key):
        if key in self:
            self.__keys.remove(key)
            self.__dirty = True
        super().__delitem__(key)

    def clear(self):
        super().clear()
        self.__keys = []
        self.__dirty = True

    def keys(self):
        if self.__dirty:
            self.__order()
        return list(self.__keys)

    def __iter__(self):
        # dict.__iter__ would hand back insertion order, which is not the
        # order this class exists to impose. Everything that walks one of
        # these -- `for k in d`, `list(d)`, `dict(d)`, `**d` -- has to see the
        # same sequence keys() does, or it silently gets a different answer.
        return iter(self.keys())

    def values(self):
        if self.__dirty:
            self.__order()
        return [self[k] for k in self.__keys]

    def items(self):
        if self.__dirty:
            self.__order()
        return [(k, self[k]) for k in self.__keys]

    def update(self, *args, **kwargs):
        if args:
            iterable = args[0]
            if hasattr(iterable, "keys"):
                for k in iterable:
                    self[k] = iterable[k]
            else:
                for k, v in iterable:
                    self[k] = v

        if kwargs:
            for k, v in kwargs.items():
                self[k] = v

    def sortingFun(self, keys):
        keys.sort()

    def __order(self):
        self.sortingFun(self.__keys)
        self.__keysLens = sorted({len(k) for k in self.__keys}, reverse=True)
        self.__dirty = False

    def nextKey(self, key):
        if self.__dirty:
            self.__order()

        keys = self.__keys

        if key in keys:
            nextIdx = keys.index(key) + 1

        else:
            nextIdx = bisect(keys, key)

        if nextIdx < len(keys):
            return keys[nextIdx]

        else:
            raise KeyError(key)

    def getKeysLens(self):
        if self.__dirty:
            self.__order()
        return self.__keysLens


class OidOrderedDict(OrderedDict):
    """OID-ordered dictionary used for indices."""

    def __init__(self, *args, **kwargs):
        """Adds a cache of key to OID tuple on top of the ordered dictionary.

        Keys arrive as tuples and as strings, and OID order is numeric per
        sub-identifier rather than lexical, so the tuple each key sorts by is
        converted once and kept.
        """
        self.__keysCache = {}
        OrderedDict.__init__(self, *args, **kwargs)

    def __setitem__(self, key, value):
        OrderedDict.__setitem__(self, key, value)
        if key not in self.__keysCache:
            if isinstance(key, tuple):
                self.__keysCache[key] = key
            else:
                self.__keysCache[key] = [int(x) for x in key.split(".") if x]

    def __delitem__(self, key):
        OrderedDict.__delitem__(self, key)
        if key in self.__keysCache:
            del self.__keysCache[key]

    def sortingFun(self, keys):
        keys.sort(key=lambda k, d=self.__keysCache: d[k])
