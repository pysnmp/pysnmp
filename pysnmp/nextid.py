#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Generators for the counters SNMP identifiers are drawn from."""

import secrets


class Integer:
    """Return a next value in a reasonably MT-safe manner."""

    def __init__(self, maximum, increment=256):
        """Draw from a bank of `increment` values, wrapping at `maximum`.

        The first value is chosen at random rather than from zero, so two
        engines started at the same moment do not issue the same identifiers.
        """
        self.__maximum = maximum
        increment = min(maximum, increment)
        self.__increment = increment
        self.__threshold = increment // 2
        e = secrets.randbelow(self.__maximum - self.__increment)
        self.__bank = list(range(e, e + self.__increment))

    def __repr__(self):
        """The constructor call that would rebuild this generator."""
        return f"{self.__class__.__name__}({self.__maximum}, {self.__increment})"

    def __call__(self):
        """The next value, refilling the bank when it runs low.

        Refilling is safe unless roughly `increment / 2` threads reach it at
        once, which is the sense in which this is only reasonably MT-safe.
        """
        v = self.__bank.pop(0)
        if v % self.__threshold:
            return v
        else:
            # this is MT-safe unless too many (~ increment/2) threads
            # bump into this code simultaneously
            e = self.__bank[-1] + 1
            if e > self.__maximum:
                e = 0
            self.__bank.extend(range(e, e + self.__threshold))
            return v
