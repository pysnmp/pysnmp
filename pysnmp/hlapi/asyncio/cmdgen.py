#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# Copyright (C) 2014, Zebra Technologies
# Authors: Matt Hooks <me@matthooks.com>
#          Zachary Lorusso <zlorusso@gmail.com>
# Modified by Ilya Etingof deceased
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
#

"""GET, GETNEXT, GETBULK and SET as coroutines."""

import asyncio
from typing import Any

from pysnmp._aliases import install as _installAliases
from pysnmp.entity.rfc3413 import cmdgen
from pysnmp.hlapi.asyncio._callback import make_callback
from pysnmp.hlapi.lcd import CommandGeneratorLcdConfigurator
from pysnmp.hlapi.types import SnmpResponse
from pysnmp.hlapi.varbinds import CommandGeneratorVarBinds

__all__ = ["bulk_cmd", "get_cmd", "is_end_of_mib", "next_cmd", "set_cmd"]

vbProcessor = CommandGeneratorVarBinds()
lcd = CommandGeneratorLcdConfigurator()


def is_end_of_mib(x):
    """Whether a walk has run off the end of every subtree it was following."""
    return not cmdgen.getNextVarBinds(x)[1]


async def get_cmd(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    *varBinds: Any,
    **options: Any,
) -> SnmpResponse:
    r"""Perform SNMP GET.

    (:RFC:`1905#section-4.2.1`)

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

    \*varBinds : :py:class:`~pysnmp.smi.rfc1902.ObjectType`
        One or more class instances representing MIB variables to place
        into SNMP request.

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

    Returns
    -------
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
    ...     result_get = await get_cmd(
    ...         SnmpEngine(),
    ...         CommunityData('public'),
    ...         UdpTransportTarget(('localhost', 161)),
    ...         ContextData(),
    ...         ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0))
    ...     )
    ...     errorIndication, errorStatus, errorIndex, varBinds = result_get
    ...     print(errorIndication, errorStatus, errorIndex, varBinds)
    >>>
    >>> # Run the coroutine against a live agent, for example:
    >>> # asyncio.run(run())

    """
    __cbFun = make_callback(vbProcessor.unmakeVarBinds)

    # Resolve before the LCD reads transportAddr. Deferred when the
    # target was built inside this loop, so that getaddrinfo() did not
    # stall it; a no-op for one built outside.
    await transportTarget.resolve()

    addrName, paramsName = lcd.configure(
        snmpEngine, authData, transportTarget, contextData.contextName
    )

    future = asyncio.get_running_loop().create_future()

    cmdgen.GetCommandGenerator().sendVarBinds(
        snmpEngine,
        addrName,
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
    return await future


async def set_cmd(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    *varBinds: Any,
    **options: Any,
) -> SnmpResponse:
    r"""Perform SNMP SET.

    (:RFC:`1905#section-4.2.5`)

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

    \*varBinds : :py:class:`~pysnmp.smi.rfc1902.ObjectType`
        One or more class instances representing MIB variables to place
        into SNMP request.

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

    Returns
    -------
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
    ...     errorIndication, errorStatus, errorIndex, varBinds = await set_cmd(
    ...         SnmpEngine(),
    ...         CommunityData('public'),
    ...         UdpTransportTarget(('localhost', 161)),
    ...         ContextData(),
    ...         ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0), 'Linux i386')
    ...     )
    ...     print(errorIndication, errorStatus, errorIndex, varBinds)
    >>>
    >>> # Run the coroutine against a live agent, for example:
    >>> # asyncio.run(run())

    """
    __cbFun = make_callback(vbProcessor.unmakeVarBinds)

    # Resolve before the LCD reads transportAddr. Deferred when the
    # target was built inside this loop, so that getaddrinfo() did not
    # stall it; a no-op for one built outside.
    await transportTarget.resolve()

    addrName, paramsName = lcd.configure(
        snmpEngine, authData, transportTarget, contextData.contextName
    )

    future = asyncio.get_running_loop().create_future()

    cmdgen.SetCommandGenerator().sendVarBinds(
        snmpEngine,
        addrName,
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
    return await future


async def next_cmd(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    *varBinds: Any,
    **options: Any,
) -> SnmpResponse:
    r"""Perform SNMP GETNEXT.

    (:RFC:`1905#section-4.2.2`)

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

    \*varBinds : :py:class:`~pysnmp.smi.rfc1902.ObjectType`
        One or more class instances representing MIB variables to place
        into SNMP request.

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

    Returns
    -------
    errorIndication : str
        True value indicates SNMP engine error.
    errorStatus : str
        True value indicates SNMP PDU error.
    errorIndex : int
        Non-zero value refers to `varBinds[errorIndex-1]`
    varBinds : tuple
        A sequence of sequences (e.g. 2-D array) of
        :py:class:`~pysnmp.smi.rfc1902.ObjectType` class instances
        representing a table of MIB variables returned in SNMP response.
        Inner sequences represent table rows and ordered exactly the same
        as `varBinds` in request. Response to GETNEXT always contain
        a single row.

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
    ...     errorIndication, errorStatus, errorIndex, varBinds = await next_cmd(
    ...         SnmpEngine(),
    ...         CommunityData('public'),
    ...         UdpTransportTarget(('localhost', 161)),
    ...         ContextData(),
    ...         ObjectType(ObjectIdentity('SNMPv2-MIB', 'system'))
    ...     )
    ...     print(errorIndication, errorStatus, errorIndex, varBinds)
    >>>
    >>> # Run the coroutine against a live agent, for example:
    >>> # asyncio.run(run())

    """
    __cbFun = make_callback(vbProcessor.unmakeVarBinds, multi_row=True)

    # Resolve before the LCD reads transportAddr. Deferred when the
    # target was built inside this loop, so that getaddrinfo() did not
    # stall it; a no-op for one built outside.
    await transportTarget.resolve()

    addrName, paramsName = lcd.configure(
        snmpEngine, authData, transportTarget, contextData.contextName
    )

    future = asyncio.get_running_loop().create_future()

    cmdgen.NextCommandGenerator().sendVarBinds(
        snmpEngine,
        addrName,
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
    return await future


async def bulk_cmd(
    snmpEngine: Any,
    authData: Any,
    transportTarget: Any,
    contextData: Any,
    nonRepeaters: Any,
    maxRepetitions: Any,
    *varBinds: Any,
    **options: Any,
) -> SnmpResponse:
    r"""Perform SNMP GETBULK.

    (:RFC:`1905#section-4.2.3`)

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

    nonRepeaters : int
        One MIB variable is requested in response for the first
        `nonRepeaters` MIB variables in request.

    maxRepetitions : int
        `maxRepetitions` MIB variables are requested in response for each
        of the remaining MIB variables in the request (e.g. excluding
        `nonRepeaters`). Remote SNMP engine may choose lesser value than
        requested.

    \*varBinds : :py:class:`~pysnmp.smi.rfc1902.ObjectType`
        One or more class instances representing MIB variables to place
        into SNMP request.

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

    Returns
    -------
    errorIndication : str
        True value indicates SNMP engine error.
    errorStatus : str
        True value indicates SNMP PDU error.
    errorIndex : int
        Non-zero value refers to `varBinds[errorIndex-1]`
    varBindTable : tuple
        A sequence of sequences (e.g. 2-D array) of
        :py:class:`~pysnmp.smi.rfc1902.ObjectType` class instances
        representing a table of MIB variables returned in SNMP response, with
        up to ``maxRepetitions`` rows, i.e.
        ``len(varBindTable) <= maxRepetitions``.

        For ``0 <= i < len(varBindTable)`` and ``0 <= j < len(varBinds)``,
        ``varBindTable[i][j]`` represents:

        - For non-repeaters (``j < nonRepeaters``), the first lexicographic
          successor of ``varBinds[j]``, regardless the value of ``i``, or an
          :py:class:`~pysnmp.smi.rfc1902.ObjectType` instance with the
          :py:obj:`~pysnmp.proto.rfc1905.endOfMibView` value if no such
          successor exists;
        - For repeaters (``j >= nonRepeaters``), the ``i``-th lexicographic
          successor of ``varBinds[j]``, or an
          :py:class:`~pysnmp.smi.rfc1902.ObjectType` instance with the
          :py:obj:`~pysnmp.proto.rfc1905.endOfMibView` value if no such
          successor exists.

        See :rfc:`3416#section-4.2.3` for details on the underlying
        ``GetBulkRequest-PDU`` and the associated ``GetResponse-PDU``, such as
        specific conditions under which the server may truncate the response,
        causing ``varBindTable`` to have less than ``maxRepetitions`` rows.

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
    ...     result_bulk = await bulk_cmd(
    ...         SnmpEngine(),
    ...         CommunityData('public'),
    ...         UdpTransportTarget(('localhost', 161)),
    ...         ContextData(),
    ...         0, 2,
    ...         ObjectType(ObjectIdentity('SNMPv2-MIB', 'system'))
    ...     )
    ...     errorIndication, errorStatus, errorIndex, varBinds = result_bulk
    ...     print(errorIndication, errorStatus, errorIndex, varBinds)
    >>>
    >>> # Run the coroutine against a live agent, for example:
    >>> # asyncio.run(run())

    """
    __cbFun = make_callback(vbProcessor.unmakeVarBinds, multi_row=True)

    # Resolve before the LCD reads transportAddr. Deferred when the
    # target was built inside this loop, so that getaddrinfo() did not
    # stall it; a no-op for one built outside.
    await transportTarget.resolve()

    addrName, paramsName = lcd.configure(
        snmpEngine, authData, transportTarget, contextData.contextName
    )

    future = asyncio.get_running_loop().create_future()

    cmdgen.BulkCommandGenerator().sendVarBinds(
        snmpEngine,
        addrName,
        contextData.contextEngineId,
        contextData.contextName,
        nonRepeaters,
        maxRepetitions,
        vbProcessor.makeVarBinds(snmpEngine, varBinds),
        __cbFun,
        (
            options.get("lookupMib", True),
            options.get("ignoreValueErrors"),
            future,
        ),
    )
    return await future


#: The camelCase spellings these names used to have. Served by ``__getattr__``
#: below rather than bound here, so that using one warns -- see
#: :py:mod:`pysnmp._aliases`.
_DEPRECATED_ALIASES = {
    "bulkCmd": "bulk_cmd",
    "getCmd": "get_cmd",
    "isEndOfMib": "is_end_of_mib",
    "nextCmd": "next_cmd",
    "setCmd": "set_cmd",
}

__getattr__, __dir__ = _installAliases(__name__, globals(), _DEPRECATED_ALIASES)
