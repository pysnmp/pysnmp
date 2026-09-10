#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""Resolving variable bindings against the MIB, in both directions."""

from typing import Any

from pysnmp.smi import view
from pysnmp.smi.rfc1902 import NotificationType, ObjectIdentity, ObjectType

__all__ = ["CommandGeneratorVarBinds", "NotificationOriginatorVarBinds"]


class AbstractVarBinds:
    @staticmethod
    def getMibViewController(snmpEngine: Any) -> Any:
        """The engine's MIB view, built and attached on first use.

        It lives on the engine rather than on the caller so every application sharing
        the engine resolves names against one index.
        """
        mibViewController = snmpEngine.getUserContext("mibViewController")
        if not mibViewController:
            mibViewController = view.MibViewController(snmpEngine.getMibBuilder())
            snmpEngine.setUserContext(mibViewController=mibViewController)
        return mibViewController


class CommandGeneratorVarBinds(AbstractVarBinds):
    """Variable bindings for requests: resolves names to OIDs and back."""

    def makeVarBinds(self, snmpEngine: Any, varBinds: Any) -> list[Any]:
        """Resolve bindings against the MIB, accepting every form a caller may pass.

        Names arrive as `ObjectType`, as an identity and value, as a bare OID, or in the
        legacy nested-tuple form, and all of them come out resolved. Errors are not
        ignored here: a request naming an object this side does not know is a mistake
        worth reporting before anything is sent.
        """
        mibViewController = self.getMibViewController(snmpEngine)
        __varBinds = []
        for varBind in varBinds:
            if isinstance(varBind, ObjectType):
                pass
            elif isinstance(varBind[0], ObjectIdentity):
                varBind = ObjectType(*varBind)
            elif isinstance(varBind[0][0], tuple):  # legacy
                varBind = ObjectType(
                    ObjectIdentity(varBind[0][0][0], varBind[0][0][1], *varBind[0][1:]),
                    varBind[1],
                )
            else:
                varBind = ObjectType(ObjectIdentity(varBind[0]), varBind[1])

            __varBinds.append(
                varBind.resolveWithMib(mibViewController, ignoreErrors=False)
            )

        return __varBinds

    def unmakeVarBinds(
        self, snmpEngine: Any, varBinds: Any, lookupMib: bool = True
    ) -> list[Any]:
        """Resolve a response's bindings back to MIB names, unless asked not to."""
        if lookupMib:
            mibViewController = self.getMibViewController(snmpEngine)
            varBinds = [
                ObjectType(ObjectIdentity(x[0]), x[1]).resolveWithMib(mibViewController)
                for x in varBinds
            ]

        return varBinds


class NotificationOriginatorVarBinds(AbstractVarBinds):
    """Variable bindings for notifications, which carry their own MIB lookups.

    Unlike the command generator, this does not resolve replies by default: a
    notification's bindings were built locally and are already what the caller
    passed in.
    """

    def makeVarBinds(self, snmpEngine: Any, varBinds: Any) -> list[Any]:
        """Resolve a notification's bindings, and the notification itself where given one."""
        mibViewController = self.getMibViewController(snmpEngine)
        if isinstance(varBinds, NotificationType):
            varBinds.resolveWithMib(mibViewController, ignoreErrors=False)
        __varBinds = []
        for varBind in varBinds:
            if isinstance(varBind, ObjectType):
                pass
            elif isinstance(varBind[0], ObjectIdentity):
                varBind = ObjectType(*varBind)
            else:
                varBind = ObjectType(ObjectIdentity(varBind[0]), varBind[1])
            __varBinds.append(
                varBind.resolveWithMib(mibViewController, ignoreErrors=False)
            )
        return __varBinds

    def unmakeVarBinds(
        self, snmpEngine: Any, varBinds: Any, lookupMib: bool = False
    ) -> list[Any]:
        """Resolve bindings back to MIB names, which for notifications is off by default.

        The bindings of a notification were built on this side and are already what the
        caller passed in, so there is normally nothing to look up.
        """
        if lookupMib:
            mibViewController = self.getMibViewController(snmpEngine)
            varBinds = [
                ObjectType(ObjectIdentity(x[0]), x[1]).resolveWithMib(mibViewController)
                for x in varBinds
            ]
        return varBinds
