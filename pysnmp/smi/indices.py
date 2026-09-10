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
        """Insert, marking the order stale where the key is new."""
        if key not in self:
            self.__keys.append(key)
            self.__dirty = True
        super().__setitem__(key, value)

    def __delitem__(self, key):
        """Remove, marking the order stale."""
        if key in self:
            self.__keys.remove(key)
            self.__dirty = True
        super().__delitem__(key)

    def clear(self):
        """Empty the mapping and forget the order."""
        super().clear()
        self.__keys = []
        self.__dirty = True

    def keys(self):
        """The keys in order, sorting first if anything has changed since the last read."""
        if self.__dirty:
            self.__order()
        return list(self.__keys)

    def __iter__(self):
        """Iterate in order, not in insertion order.

        `dict.__iter__` would hand back insertion order, which is not the order this
        class exists to impose. Everything that walks a mapping goes through here, so
        overriding it is what keeps `list(d)`, `dict(d)` and `**d` agreeing with
        `keys()`.
        """
        # dict.__iter__ would hand back insertion order, which is not the
        # order this class exists to impose. Everything that walks one of
        # these -- `for k in d`, `list(d)`, `dict(d)`, `**d` -- has to see the
        # same sequence keys() does, or it silently gets a different answer.
        return iter(self.keys())

    def values(self):
        """The values, in key order."""
        if self.__dirty:
            self.__order()
        return [self[k] for k in self.__keys]

    def items(self):
        """The pairs, in key order."""
        if self.__dirty:
            self.__order()
        return [(k, self[k]) for k in self.__keys]

    def update(self, *args, **kwargs):
        """Insert from a mapping or from pairs, one key at a time.

        Each key goes through `__setitem__` rather than `dict.update`, since that is
        what maintains the key order and, in the OID subclass, the sort cache.
        """
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
        """Sort the keys in place. Subclasses override this to order differently."""
        keys.sort()

    def __order(self):
        """Sort the keys and note the distinct key lengths, longest first."""
        self.sortingFun(self.__keys)
        self.__keysLens = sorted({len(k) for k in self.__keys}, reverse=True)
        self.__dirty = False

    def nextKey(self, key):
        """The key after this one, whether or not this one is present.

        GETNEXT asks for the successor of an OID that need not exist, which is the whole
        reason for keeping the keys ordered. Raises `KeyError` past the last key.
        """
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
        """The distinct key lengths, longest first.

        Resolving an OID to a table row means trying successively shorter prefixes, and
        only these lengths can possibly match.
        """
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
        """Insert, caching the OID tuple this key will sort by.

        Keys arrive both as tuples and as dotted strings, and the sort needs the numeric
        form of each; converting once here keeps it off the comparison path.
        """
        OrderedDict.__setitem__(self, key, value)
        if key not in self.__keysCache:
            if isinstance(key, tuple):
                self.__keysCache[key] = key
            else:
                self.__keysCache[key] = [int(x) for x in key.split(".") if x]

    def __delitem__(self, key):
        """Remove, dropping the cached OID tuple with it."""
        OrderedDict.__delitem__(self, key)
        if key in self.__keysCache:
            del self.__keysCache[key]

    def sortingFun(self, keys):
        """Sort by OID component rather than lexically.

        This is what puts 1.3.6.1.10 after 1.3.6.1.9 instead of before it, and a walk
        that sorted the other way would return rows in the wrong order and never
        terminate correctly.
        """
        keys.sort(key=lambda k, d=self.__keysCache: d[k])
