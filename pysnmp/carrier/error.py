#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Errors raised by transports and dispatchers."""

from pysnmp import error


class CarrierError(error.PySnmpError):
    """Raised when a transport or dispatcher cannot do what was asked of it."""

    pass
