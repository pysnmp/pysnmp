"""The synchronous facade: the same calls, run to completion on a private loop."""

from pysnmp._aliases import install as _installAliases
from pysnmp.hlapi.asyncio.sync.cmdgen import bulk_cmd, get_cmd, next_cmd, set_cmd
from pysnmp.hlapi.asyncio.sync.device import get_device_report
from pysnmp.hlapi.asyncio.sync.dh import dh_key_change
from pysnmp.hlapi.asyncio.sync.ntforg import send_notification
from pysnmp.hlapi.asyncio.transport import (
    Tcp6TransportTarget,
    TcpTransportTarget,
    Udp6TransportTarget,
    UdpTransportTarget,
    UnixTransportTarget,
)

#: The camelCase spellings these names used to have. Served by ``__getattr__``
#: below rather than bound here, so that using one warns -- see
#: :py:mod:`pysnmp._aliases`.
_DEPRECATED_ALIASES = {
    "bulkCmd": "bulk_cmd",
    "dhKeyChange": "dh_key_change",
    "getCmd": "get_cmd",
    "getDeviceReport": "get_device_report",
    "nextCmd": "next_cmd",
    "sendNotification": "send_notification",
    "setCmd": "set_cmd",
}

__getattr__, __dir__ = _installAliases(__name__, globals(), _DEPRECATED_ALIASES)
