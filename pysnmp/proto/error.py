#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Errors raised while processing a message."""

from pyasn1.error import PyAsn1Error

from pysnmp import debug
from pysnmp.error import PySnmpError


class ProtocolError(PySnmpError, PyAsn1Error):
    """Raised when a message cannot be processed."""

    pass


# SNMP v3 exceptions


class SnmpV3Error(ProtocolError):
    """Raised by the SNMPv3 machinery: message processing, security, access control."""

    pass


class StatusInformation(SnmpV3Error):
    """Carries how a step failed, and what the next step needs to know.

    Not always a failure the caller sees: the v3 discovery exchange reports back
    through this, and the engine reads the details off it like a mapping to decide
    whether to send a report, reissue the request, or give up.
    """

    def __init__(self, **kwargs):
        SnmpV3Error.__init__(self)
        self.__errorIndication = kwargs
        debug.logger & (
            debug.flagDsp | debug.flagMP | debug.flagSM | debug.flagACL
        ) and debug.logger(f"StatusInformation: {kwargs}")

    def __str__(self):
        return str(self.__errorIndication)

    def __getitem__(self, key):
        return self.__errorIndication[key]

    def __contains__(self, key):
        return key in self.__errorIndication

    def get(self, key, defVal=None):
        return self.__errorIndication.get(key, defVal)


class CacheExpiredError(SnmpV3Error):
    """The state this message refers to is gone, so it can no longer be answered."""

    pass


class InternalError(SnmpV3Error):
    """Something the engine assumed about its own state did not hold."""

    pass


class MessageProcessingError(SnmpV3Error):
    """The message could not be prepared or parsed."""

    pass


class RequestTimeout(SnmpV3Error):
    """No response arrived in time."""

    pass
