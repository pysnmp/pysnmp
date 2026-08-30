#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi import auth
from pysnmp.hlapi.asyncio.device import DeviceReport as DeviceReport
from pysnmp.hlapi.asyncio.device import SysOREntry as SysOREntry

# default is a synchronous facade over the asyncio API
from pysnmp.hlapi.asyncio.sync import (
    UnixTransportTarget,
    Udp6TransportTarget,
    UdpTransportTarget,
    bulkCmd,
    get_device_report,
    getCmd,
    getDeviceReport,
    nextCmd,
    sendNotification,
    setCmd,
)
from pysnmp.hlapi.context import ContextData
from pysnmp.proto.rfc1902 import (
    Bits,
    Counter32,
    Counter64,
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
)
from pysnmp.proto.rfc1905 import EndOfMibView, NoSuchInstance, NoSuchObject
from pysnmp.smi.rfc1902 import NotificationType, ObjectIdentity, ObjectType

CommunityData = auth.CommunityData
UsmUserData = auth.UsmUserData

usmNoAuthProtocol = auth.usmNoAuthProtocol
"""No Authentication Protocol"""

usmHMACMD5AuthProtocol = auth.usmHMACMD5AuthProtocol
"""The HMAC-MD5-96 Digest Authentication Protocol (:RFC:`3414#section-6`)"""

usmHMACSHAAuthProtocol = auth.usmHMACSHAAuthProtocol
"""The HMAC-SHA-96 Digest Authentication Protocol AKA SHA-1 (:RFC:`3414#section-7`)"""

usmHMAC128SHA224AuthProtocol = auth.usmHMAC128SHA224AuthProtocol
"""The HMAC-SHA-2 Digest Authentication Protocols (:RFC:`7860`)"""

usmHMAC192SHA256AuthProtocol = auth.usmHMAC192SHA256AuthProtocol
"""The HMAC-SHA-2 Digest Authentication Protocols (:RFC:`7860`)"""

usmHMAC256SHA384AuthProtocol = auth.usmHMAC256SHA384AuthProtocol
"""The HMAC-SHA-2 Digest Authentication Protocols (:RFC:`7860`)"""

usmHMAC384SHA512AuthProtocol = auth.usmHMAC384SHA512AuthProtocol
"""The HMAC-SHA-2 Digest Authentication Protocols (:RFC:`7860`)"""

usmNoPrivProtocol = auth.usmNoPrivProtocol
"""No Privacy Protocol"""

usmDESPrivProtocol = auth.usmDESPrivProtocol
"""The CBC-DES Symmetric Encryption Protocol (:RFC:`3414#section-8`)"""

usm3DESEDEPrivProtocol = auth.usm3DESEDEPrivProtocol
"""The 3DES-EDE Symmetric Encryption Protocol (`draft-reeder-snmpv3-usm-3desede-00 <https:://tools.ietf.org/html/draft-reeder-snmpv3-usm-3desede-00#section-5>`_)"""

usmAesCfb128Protocol = auth.usmAesCfb128Protocol
"""The CFB128-AES-128 Symmetric Encryption Protocol (:RFC:`3826#section-3`)"""

usmAesCfb192Protocol = auth.usmAesCfb192Protocol
"""The CFB128-AES-192 Symmetric Encryption Protocol (`draft-blumenthal-aes-usm-04 <https:://tools.ietf.org/html/draft-blumenthal-aes-usm-04#section-3>`_) with Reeder key localization"""

usmAesCfb256Protocol = auth.usmAesCfb256Protocol
"""The CFB128-AES-256 Symmetric Encryption Protocol (`draft-blumenthal-aes-usm-04 <https:://tools.ietf.org/html/draft-blumenthal-aes-usm-04#section-3>`_) with Reeder key localization"""

usmAesBlumenthalCfb192Protocol = auth.usmAesBlumenthalCfb192Protocol
"""The CFB128-AES-192 Symmetric Encryption Protocol (`draft-blumenthal-aes-usm-04 <https:://tools.ietf.org/html/draft-blumenthal-aes-usm-04#section-3>`_)"""

usmAesBlumenthalCfb256Protocol = auth.usmAesBlumenthalCfb256Protocol
"""The CFB128-AES-256 Symmetric Encryption Protocol (`draft-blumenthal-aes-usm-04 <https:://tools.ietf.org/html/draft-blumenthal-aes-usm-04#section-3>`_)"""

usmKeyTypePassphrase = auth.usmKeyTypePassphrase
"""USM key material type - plain-text pass phrase (:RFC:`3414#section-2.6`)"""

usmKeyTypeMaster = auth.usmKeyTypeMaster
"""USM key material type - hashed pass-phrase AKA master key (:RFC:`3414#section-2.6`)"""

usmKeyTypeLocalized = auth.usmKeyTypeLocalized
"""USM key material type - hashed pass-phrase hashed with Context SNMP Engine ID (:RFC:`3414#section-2.6`)"""
