#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# Copyright (C) 2014, Zebra Technologies
# Authors: Matt Hooks <me@matthooks.com>
#          Zachary Lorusso <zlorusso@gmail.com>
#

"""Sending traps and informs as a coroutine."""

import asyncio
from typing import Any

from pysnmp._aliases import install as _installAliases
from pysnmp.entity.rfc3413 import ntforg
from pysnmp.hlapi.asyncio._callback import make_callback
from pysnmp.hlapi.lcd import NotificationOriginatorLcdConfigurator
from pysnmp.hlapi.types import SnmpResponse
from pysnmp.hlapi.varbinds import NotificationOriginatorVarBinds

__all__ = ["send_notification"]

vbProcessor = NotificationOriginatorVarBinds()
lcd = NotificationOriginatorLcdConfigurator()


async def send_notification(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    notifyType: str,
    varBinds: Any,
    **options: Any,
) -> SnmpResponse:
    r"""Send SNMP notification.

    Parameters
    ----------
    snmpEngine : :py:class:`~pysnmp.hlapi.SnmpEngine`
        Class instance representing SNMP engine.

    authData : :py:class:`~pysnmp.hlapi.CommunityData` or :py:class:`~pysnmp.hlapi.UsmUserData`
        Class instance representing SNMP credentials.

    transportTarget : :py:class:`~pysnmp.hlapi.asyncio.UdpTransportTarget` or :py:class:`~pysnmp.hlapi.asyncio.Udp6TransportTarget`
        Class instance representing transport type along with SNMP peer address.

    contextData : :py:class:`~pysnmp.hlapi.ContextData`
        Class instance representing SNMP ContextEngineId and ContextName values.

    notifyType : str
        Indicates type of notification to be sent. Recognized literal
        values are *trap* or *inform*.

    varBinds: tuple
        Single :py:class:`~pysnmp.smi.rfc1902.NotificationType` class instance
        representing a minimum sequence of MIB variables required for
        particular notification type.
        Alternatively, a sequence of :py:class:`~pysnmp.smi.rfc1902.ObjectType`
        objects could be passed instead. In the latter case it is up to
        the user to ensure proper Notification PDU contents.

    Other Parameters
    ----------------
    \*\*options :
        Request options:

            * `lookupMib` - load MIB and resolve response MIB variables at
              the cost of slightly reduced performance. Default is `True`.

            * `ignoreValueErrors` - what to do about a response value that
              will not cast to the syntax its MIB object declares. Default is
              `None`, which tolerates it and hands back the uncast value.
              `False` reports it as
              :py:class:`~pysnmp.smi.error.SmiError` instead.

              A name the peer answered under a MIB this side has not loaded is
              a different matter and stays tolerated either way: it comes back
              as a bare OID, because raising would end a walk at the first such
              binding. Only `lookupMib` turns resolution off altogether.

    Result
    ------
    errorIndication : str
        True value indicates SNMP engine error.
    errorStatus : str
        True value indicates SNMP PDU error.
    errorIndex : int
        Non-zero value refers to `varBinds[errorIndex-1]`
    varBinds : tuple
        A sequence of :py:class:`~pysnmp.smi.rfc1902.ObjectType` class
        instances representing MIB variables returned in SNMP response.

    Raises
    ------
    pysnmp.error.PySnmpError
        Or its derivative indicating that an error occurred while
        performing SNMP operation.

    Examples
    --------
    >>> import asyncio
    >>> from pysnmp.hlapi.asyncio import *
    >>>
    >>> async def run():
    ...     send_result = await send_notification(
    ...         SnmpEngine(),
    ...         CommunityData('public'),
    ...         UdpTransportTarget(('localhost', 162)),
    ...         ContextData(),
    ...         'trap',
    ...         NotificationType(ObjectIdentity('IF-MIB', 'linkDown')))
    ...     errorIndication, errorStatus, errorIndex, varBinds = send_result
    ...     print(errorIndication, errorStatus, errorIndex, varBinds)
    ...
    >>> # Run the coroutine against a live agent, for example:
    >>> # asyncio.run(run())

    """
    __cbFun = make_callback(vbProcessor.unmakeVarBinds)

    # Resolve before the LCD reads transportAddr. Deferred when the
    # target was built inside this loop, so that getaddrinfo() did not
    # stall it; a no-op for one built outside.
    await transportTarget.resolve()

    notifyName = lcd.configure(
        snmpEngine, authData, transportTarget, notifyType, contextData.contextName
    )

    future = asyncio.get_running_loop().create_future()

    ntforg.NotificationOriginator().sendVarBinds(
        snmpEngine,
        notifyName,
        contextData.contextEngineId,
        contextData.contextName,
        vbProcessor.makeVarBinds(snmpEngine, varBinds),
        __cbFun,
        (
            options.get("lookupMib", True),
            options.get("ignoreValueErrors"),
            future,
        ),
    )

    if notifyType == "trap":

        def __trapFun(future):
            if future.cancelled():
                return
            future.set_result((None, 0, 0, []))

        loop = asyncio.get_running_loop()
        loop.call_soon(__trapFun, future)

    return await future


#: The camelCase spelling this name used to have. Served by ``__getattr__``
#: below rather than bound here, so that using it warns -- see
#: :py:mod:`pysnmp._aliases`.
_DEPRECATED_ALIASES = {"sendNotification": "send_notification"}

__getattr__, __dir__ = _installAliases(__name__, globals(), _DEPRECATED_ALIASES)
