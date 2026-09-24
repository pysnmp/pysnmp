#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The high-level API as coroutines.

Same calls as `pysnmp.hlapi`, awaited rather than blocking.
"""

from pysnmp._aliases import install as _installAliases
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.asyncio.cmdgen import (
    bulk_cmd,
    bulk_walk_cmd,
    get_cmd,
    is_end_of_mib,
    next_cmd,
    set_cmd,
    walk_cmd,
)
from pysnmp.hlapi.asyncio.device import (
    DeviceReport,
    SysOREntry,
    get_device_report,
)
from pysnmp.hlapi.asyncio.dh import (
    DHKeyChangeError,
    DHKeyChangeResult,
    dh_key_change,
)
from pysnmp.hlapi.asyncio.ntforg import send_notification
from pysnmp.hlapi.asyncio.transport import (
    Tcp6TransportTarget,
    TcpTransportTarget,
    Udp6TransportTarget,
    UdpTransportTarget,
    UnixTransportTarget,
)
from pysnmp.hlapi.auth import (
    CommunityData,
    UsmUserData,
    usm3DESEDEPrivProtocol,
    usmAesBlumenthalCfb192Protocol,
    usmAesBlumenthalCfb256Protocol,
    usmAesCfb128Protocol,
    usmAesCfb192Protocol,
    usmAesCfb256Protocol,
    usmDESPrivProtocol,
    usmHMAC128SHA224AuthProtocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
    usmNoAuthProtocol,
    usmNoPrivProtocol,
)
from pysnmp.hlapi.context import ContextData
from pysnmp.proto.rfc1902 import (
    Bits,
    Counter32,
    Counter64,
    Double,
    Float,
    Gauge32,
    Integer,
    Integer32,
    IpAddress,
    Null,
    ObjectIdentifier,
    OctetString,
    Opaque,
    TimeTicks,
    Unsigned32,
    decodeOpaque,
)
from pysnmp.smi.rfc1902 import NotificationType, ObjectIdentity, ObjectType

#: The camelCase spellings these names used to have. Served by ``__getattr__``
#: below rather than bound here, so that using one warns -- see
#: :py:mod:`pysnmp._aliases`.
_DEPRECATED_ALIASES = {
    "bulkCmd": "bulk_cmd",
    "bulkWalkCmd": "bulk_walk_cmd",
    "dhKeyChange": "dh_key_change",
    "getCmd": "get_cmd",
    "getDeviceReport": "get_device_report",
    "isEndOfMib": "is_end_of_mib",
    "nextCmd": "next_cmd",
    "sendNotification": "send_notification",
    "setCmd": "set_cmd",
    "walkCmd": "walk_cmd",
}

__getattr__, __dir__ = _installAliases(__name__, globals(), _DEPRECATED_ALIASES)
