#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Shared type definitions for the pysnmp high-level API.

These types are used across the sync and asyncio HLAPI surfaces to
provide consistent return-type annotations for SNMP command results.
"""

from typing import Any, NamedTuple

__all__ = ['SnmpResponse']


class SnmpResponse(NamedTuple):
    """Result of an SNMP command (GET / SET / NEXT / BULK / notification).

    This is a ``NamedTuple`` subclass of ``tuple``, so existing code that
    unpacks the 4-tuple positionally continues to work unchanged::

        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(...)

    Attributes
    ----------
    errorIndication
        ``None`` on success, or an error-indication object/string on
        SNMP engine error.
    errorStatus
        ``0`` / ``None`` on success, or a truthy value indicating a
        protocol-level PDU error.
    errorIndex
        ``0`` when no error, otherwise a 1-based index into *varBinds*
        referring to the variable that caused the error.
    varBinds
        A sequence of resolved var-bind pairs (typically
        :class:`~pysnmp.smi.rfc1902.ObjectType` instances).
    """

    errorIndication: Any
    errorStatus: Any
    errorIndex: Any
    varBinds: Any
