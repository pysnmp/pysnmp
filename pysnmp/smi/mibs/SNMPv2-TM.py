#
# PySNMP MIB module SNMPv2-TM (https://pysnmp.github.io/pysmi/)
# ASN.1 source SNMPv2-TM
# Source digest sha256:e3595f02a62df624193839267143db221ab9847440c74bae2b09af149f9c5284
# Produced by pysmi-5.6.0
#
PYSNMP_MODULE_REVISION = "200210160000Z"

Integer, ObjectIdentifier, OctetString = mibBuilder.importSymbols(
    "ASN1", "Integer", "ObjectIdentifier", "OctetString"
)
(NamedValues,) = mibBuilder.importSymbols("ASN1-ENUMERATION", "NamedValues")
(
    ConstraintsIntersection,
    ConstraintsUnion,
    SingleValueConstraint,
    ValueRangeConstraint,
    ValueSizeConstraint,
) = mibBuilder.importSymbols(
    "ASN1-REFINEMENT",
    "ConstraintsIntersection",
    "ConstraintsUnion",
    "SingleValueConstraint",
    "ValueRangeConstraint",
    "ValueSizeConstraint",
)
ModuleCompliance, NotificationGroup = mibBuilder.importSymbols(
    "SNMPv2-CONF", "ModuleCompliance", "NotificationGroup"
)
(
    Bits,
    Counter32,
    Counter64,
    Gauge32,
    Integer32,
    IpAddress,
    ModuleIdentity,
    MibIdentifier,
    NotificationType,
    ObjectIdentity,
    MibScalar,
    MibTable,
    MibTableRow,
    MibTableColumn,
    TimeTicks,
    Unsigned32,
    iso,
    snmpDomains,
    snmpModules,
    snmpProxys,
) = mibBuilder.importSymbols(
    "SNMPv2-SMI",
    "Bits",
    "Counter32",
    "Counter64",
    "Gauge32",
    "Integer32",
    "IpAddress",
    "ModuleIdentity",
    "MibIdentifier",
    "NotificationType",
    "ObjectIdentity",
    "MibScalar",
    "MibTable",
    "MibTableRow",
    "MibTableColumn",
    "TimeTicks",
    "Unsigned32",
    "iso",
    "snmpDomains",
    "snmpModules",
    "snmpProxys",
)
DisplayString, TextualConvention = mibBuilder.importSymbols(
    "SNMPv2-TC", "DisplayString", "TextualConvention"
)
snmpv2tm = ModuleIdentity((1, 3, 6, 1, 6, 3, 19))
snmpv2tm.setRevisions(
    (
        "2002-10-16 00:00",
        "1996-01-01 00:00",
        "1993-04-01 00:00",
    )
)
if mibBuilder.loadTexts:
    snmpv2tm.setRevisionsDescriptions(
        (
            "Clarifications, published as RFC 3417.",
            "Clarifications, published as RFC 1906.",
            "The initial version, published as RFC 1449.",
        )
    )
if mibBuilder.loadTexts:
    snmpv2tm.setLastUpdated("2002-10-16 00:00")
if mibBuilder.loadTexts:
    snmpv2tm.setOrganization("IETF SNMPv3 Working Group")
if mibBuilder.loadTexts:
    snmpv2tm.setContactInfo(
        "WG-EMail: snmpv3@lists.tislabs.com Subscribe: snmpv3-request@lists.tislabs.com Co-Chair: Russ Mundy Network Associates Laboratories postal: 15204 Omega Drive, Suite 300 Rockville, MD 20850-4601 USA EMail: mundy@tislabs.com phone: +1 301 947-7107 Co-Chair: David Harrington Enterasys Networks postal: 35 Industrial Way P. O. Box 5005 Rochester, NH 03866-5005 USA EMail: dbh@enterasys.com phone: +1 603 337-2614 Editor: Randy Presuhn BMC Software, Inc. postal: 2141 North First Street San Jose, CA 95131 USA EMail: randy_presuhn@bmc.com phone: +1 408 546-1006"
    )
if mibBuilder.loadTexts:
    snmpv2tm.setDescription(
        "The MIB module for SNMP transport mappings. Copyright (C) The Internet Society (2002). This version of this MIB module is part of RFC 3417; see the RFC itself for full legal notices. "
    )
snmpUDPDomain = ObjectIdentity((1, 3, 6, 1, 6, 1, 1))
if mibBuilder.loadTexts:
    snmpUDPDomain.setStatus("current")
if mibBuilder.loadTexts:
    snmpUDPDomain.setDescription(
        "The SNMP over UDP over IPv4 transport domain. The corresponding transport address is of type SnmpUDPAddress."
    )


class SnmpUDPAddress(TextualConvention, OctetString):
    description = "Represents a UDP over IPv4 address: octets contents encoding 1-4 IP-address network-byte order 5-6 UDP-port network-byte order "
    status = "current"
    displayHint = "1d.1d.1d.1d/2d"
    subtypeSpec = OctetString.subtypeSpec + ValueSizeConstraint(6, 6)
    fixedLength = 6


snmpCLNSDomain = ObjectIdentity((1, 3, 6, 1, 6, 1, 2))
if mibBuilder.loadTexts:
    snmpCLNSDomain.setStatus("current")
if mibBuilder.loadTexts:
    snmpCLNSDomain.setDescription(
        "The SNMP over CLNS transport domain. The corresponding transport address is of type SnmpOSIAddress."
    )
snmpCONSDomain = ObjectIdentity((1, 3, 6, 1, 6, 1, 3))
if mibBuilder.loadTexts:
    snmpCONSDomain.setStatus("current")
if mibBuilder.loadTexts:
    snmpCONSDomain.setDescription(
        "The SNMP over CONS transport domain. The corresponding transport address is of type SnmpOSIAddress."
    )


class SnmpOSIAddress(TextualConvention, OctetString):
    description = "Represents an OSI transport-address: octets contents encoding 1 length of NSAP 'n' as an unsigned-integer (either 0 or from 3 to 20) 2..(n+1) NSAP concrete binary representation (n+2)..m TSEL string of (up to 64) octets "
    status = "current"
    displayHint = "*1x:/1x:"
    subtypeSpec = OctetString.subtypeSpec + ConstraintsUnion(
        ValueSizeConstraint(1, 1),
        ValueSizeConstraint(4, 85),
    )


snmpDDPDomain = ObjectIdentity((1, 3, 6, 1, 6, 1, 4))
if mibBuilder.loadTexts:
    snmpDDPDomain.setStatus("current")
if mibBuilder.loadTexts:
    snmpDDPDomain.setDescription(
        "The SNMP over DDP transport domain. The corresponding transport address is of type SnmpNBPAddress."
    )


class SnmpNBPAddress(TextualConvention, OctetString):
    description = "Represents an NBP name: octets contents encoding 1 length of object 'n' as an unsigned integer 2..(n+1) object string of (up to 32) octets n+2 length of type 'p' as an unsigned integer (n+3)..(n+2+p) type string of (up to 32) octets n+3+p length of zone 'q' as an unsigned integer (n+4+p)..(n+3+p+q) zone string of (up to 32) octets For comparison purposes, strings are case-insensitive. All strings may contain any octet other than 255 (hex ff)."
    status = "current"
    subtypeSpec = OctetString.subtypeSpec + ValueSizeConstraint(3, 99)


snmpIPXDomain = ObjectIdentity((1, 3, 6, 1, 6, 1, 5))
if mibBuilder.loadTexts:
    snmpIPXDomain.setStatus("current")
if mibBuilder.loadTexts:
    snmpIPXDomain.setDescription(
        "The SNMP over IPX transport domain. The corresponding transport address is of type SnmpIPXAddress."
    )


class SnmpIPXAddress(TextualConvention, OctetString):
    description = "Represents an IPX address: octets contents encoding 1-4 network-number network-byte order 5-10 physical-address network-byte order 11-12 socket-number network-byte order "
    status = "current"
    displayHint = "4x.1x:1x:1x:1x:1x:1x.2d"
    subtypeSpec = OctetString.subtypeSpec + ValueSizeConstraint(12, 12)
    fixedLength = 12


rfc1157Proxy = MibIdentifier((1, 3, 6, 1, 6, 2, 1))
rfc1157Domain = ObjectIdentity((1, 3, 6, 1, 6, 2, 1, 1))
if mibBuilder.loadTexts:
    rfc1157Domain.setStatus("deprecated")
if mibBuilder.loadTexts:
    rfc1157Domain.setDescription(
        "The transport domain for SNMPv1 over UDP over IPv4. The corresponding transport address is of type SnmpUDPAddress."
    )
mibBuilder.exportSymbols(
    "SNMPv2-TM",
    PYSNMP_MODULE_ID=snmpv2tm,
    SnmpIPXAddress=SnmpIPXAddress,
    SnmpNBPAddress=SnmpNBPAddress,
    SnmpOSIAddress=SnmpOSIAddress,
    SnmpUDPAddress=SnmpUDPAddress,
    rfc1157Domain=rfc1157Domain,
    rfc1157Proxy=rfc1157Proxy,
    snmpCLNSDomain=snmpCLNSDomain,
    snmpCONSDomain=snmpCONSDomain,
    snmpDDPDomain=snmpDDPDomain,
    snmpIPXDomain=snmpIPXDomain,
    snmpUDPDomain=snmpUDPDomain,
    snmpv2tm=snmpv2tm,
)
