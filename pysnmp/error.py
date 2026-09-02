#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

import sys


class PySnmpCryptoWarning(UserWarning):
    """Base class for warnings about SNMPv3 cryptographic protocol selection.

    Subclasses of this warning are raised at user configuration time rather
    than at packet processing time. They derive from `UserWarning` (not
    `DeprecationWarning`) so that they remain visible under Python's default
    warning filters, since ignoring them has security consequences.
    """


class PySnmpWeakCryptoWarning(PySnmpCryptoWarning):
    """The selected protocol is no longer considered cryptographically safe."""


class PySnmpNonStandardCryptoWarning(PySnmpCryptoWarning):
    """The selected protocol is not standards-track and may not interoperate."""


class PySnmpError(Exception):
    def __init__(self, *args):
        msg = args and str(args[0]) or ""

        self.cause = sys.exc_info()

        if self.cause[0]:
            msg += f"caused by {self.cause[0]}: {self.cause[1]}"

        if msg:
            args = (msg,) + args[1:]

        super().__init__(*args)
