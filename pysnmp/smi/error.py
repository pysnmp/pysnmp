#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Errors raised while loading MIBs or serving managed objects.

The `MibOperationError` subclasses map onto the SNMP error statuses an agent
returns, so raising one is how instrumentation reports a failure.
"""

from pyasn1.error import PyAsn1Error

from pysnmp.error import PySnmpError


class SmiError(PySnmpError, PyAsn1Error):
    """Raised when a MIB cannot be loaded or a managed object cannot be served."""

    pass


class MibLoadError(SmiError):
    """Raised when a MIB module was found but could not be loaded."""

    pass


class MibNotFoundError(MibLoadError):
    """Raised when no source holds the MIB module that was asked for."""

    pass


class MibOperationError(SmiError):
    """Raised while serving a managed object, carrying named details.

    The details are what the caller needs to build a response -- which binding
    failed, what the old value was -- and are read off the exception like a
    mapping. Subclasses are the SNMP error statuses of :RFC:`3416#section-3`.
    """

    def __init__(self, **kwargs):
        """Details are kept as given and read back like a mapping."""
        self.__outArgs = kwargs

    def __str__(self):
        """The class name and everything the error was given."""
        return f"{self.__class__.__name__}({self.__outArgs})"

    def __getitem__(self, key):
        """One detail of the error."""
        return self.__outArgs[key]

    def __contains__(self, key):
        """Whether a detail was set."""
        return key in self.__outArgs

    def get(self, key, defVal=None):
        """One detail, or `defVal` where it was not set."""
        return self.__outArgs.get(key, defVal)

    def keys(self):
        """The details that were set."""
        return self.__outArgs.keys()

    def update(self, d):
        """Add details to the error, which is how an error picks up context as it rises."""
        self.__outArgs.update(d)


# Aligned with SNMPv2 PDU error-status values


class TooBigError(MibOperationError):
    """The response would not fit in one message."""

    pass


class NoSuchNameError(MibOperationError):
    """No such object, as SNMPv1 reports it."""

    pass


class BadValueError(MibOperationError):
    """The value is not acceptable for the object, as SNMPv1 reports it."""

    pass


class ReadOnlyError(MibOperationError):
    """The object cannot be written, as SNMPv1 reports it."""

    pass


class GenError(MibOperationError):
    """Something else went wrong."""

    pass


class NoAccessError(MibOperationError):
    """The object is not accessible to this request."""

    pass


class WrongTypeError(MibOperationError):
    """The value is of the wrong type for the object."""

    pass


class WrongLengthError(MibOperationError):
    """The value is the right type but the wrong length."""

    pass


class WrongEncodingError(MibOperationError):
    """The value is not encoded the way its type requires."""

    pass


class WrongValueError(MibOperationError):
    """The value is well-formed but outside what the object accepts."""

    pass


class NoCreationError(MibOperationError):
    """The instance does not exist and cannot be created."""

    pass


class InconsistentValueError(MibOperationError):
    """The value is valid on its own but not against the rest of the state."""

    pass


class ResourceUnavailableError(MibOperationError):
    """The write needs a resource that is not available."""

    pass


class CommitFailedError(MibOperationError):
    """The write passed its checks but could not be committed."""

    pass


class UndoFailedError(MibOperationError):
    """A commit failed and undoing it failed too."""

    pass


class AuthorizationError(MibOperationError):
    """The request is not authorized."""

    pass


class NotWritableError(MibOperationError):
    """The object is not writable, as SNMPv2c and later report it."""

    pass


class InconsistentNameError(MibOperationError):
    """The instance name is inconsistent with the rest of the row."""

    pass


# Aligned with SNMPv2 PDU exceptions or error-status values


class NoSuchObjectError(NoSuchNameError):
    """No such object in this view, the SNMPv2c `noSuchObject` exception."""

    pass


class NoSuchInstanceError(NoSuchNameError):
    """The object exists but has no such instance, `noSuchInstance`."""

    pass


class EndOfMibViewError(NoSuchNameError):
    """There is nothing past this OID, the `endOfMibView` exception."""

    pass


# SNMP table management exceptions


class TableRowManagement(MibOperationError):
    """Raised to ask the caller to create or destroy a conceptual row.

    Not a failure: a write to a RowStatus column is how SNMP asks for a row to
    appear or go away, and this is how the column tells the table about it.
    """

    pass


class RowCreationWanted(TableRowManagement):
    """A row should be created."""

    pass


class RowDestructionWanted(TableRowManagement):
    """A row should be destroyed."""

    pass
