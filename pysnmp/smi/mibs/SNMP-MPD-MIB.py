#
# PySNMP MIB module SNMP-MPD-MIB (http://snmplabs.com/pysmi)
# ASN.1 source SNMP-MPD-MIB
# Source digest sha256:9eb9f3324c9c345fe0ee57b1bb0879ae8e52594756f27534d447d20342d60364
# Produced by pysmi-4.0.0-rc.4
#
PYSNMP_MODULE_REVISION = "200210140000Z"

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
ModuleCompliance, NotificationGroup, ObjectGroup = mibBuilder.importSymbols(
    "SNMPv2-CONF", "ModuleCompliance", "NotificationGroup", "ObjectGroup"
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
    snmpModules,
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
    "snmpModules",
)
DisplayString, TextualConvention = mibBuilder.importSymbols(
    "SNMPv2-TC", "DisplayString", "TextualConvention"
)
snmpMPDMIB = ModuleIdentity((1, 3, 6, 1, 6, 3, 11))
snmpMPDMIB.setRevisions(
    (
        "2002-10-14 00:00",
        "1999-05-04 16:36",
        "1997-09-30 00:00",
    )
)
if mibBuilder.loadTexts:
    snmpMPDMIB.setRevisionsDescriptions(
        (
            "Updated addresses, published as RFC 3412.",
            "Updated addresses, published as RFC 2572.",
            "Original version, published as RFC 2272.",
        )
    )
if mibBuilder.loadTexts:
    snmpMPDMIB.setLastUpdated("2002-10-14 00:00")
if mibBuilder.loadTexts:
    snmpMPDMIB.setOrganization("SNMPv3 Working Group")
if mibBuilder.loadTexts:
    snmpMPDMIB.setContactInfo(
        "WG-EMail: snmpv3@lists.tislabs.com Subscribe: snmpv3-request@lists.tislabs.com Co-Chair: Russ Mundy Network Associates Laboratories postal: 15204 Omega Drive, Suite 300 Rockville, MD 20850-4601 USA EMail: mundy@tislabs.com phone: +1 301-947-7107 Co-Chair & Co-editor: David Harrington Enterasys Networks postal: 35 Industrial Way P. O. Box 5005 Rochester NH 03866-5005 USA EMail: dbh@enterasys.com phone: +1 603-337-2614 Co-editor: Jeffrey Case SNMP Research, Inc. postal: 3001 Kimberlin Heights Road Knoxville, TN 37920-9716 USA EMail: case@snmp.com phone: +1 423-573-1434 Co-editor: Randy Presuhn BMC Software, Inc. postal: 2141 North First Street San Jose, CA 95131 USA EMail: randy_presuhn@bmc.com phone: +1 408-546-1006 Co-editor: Bert Wijnen Lucent Technologies postal: Schagen 33 3461 GL Linschoten Netherlands EMail: bwijnen@lucent.com phone: +31 348-680-485 "
    )
if mibBuilder.loadTexts:
    snmpMPDMIB.setDescription(
        "The MIB for Message Processing and Dispatching Copyright (C) The Internet Society (2002). This version of this MIB module is part of RFC 3412; see the RFC itself for full legal notices. "
    )
snmpMPDAdmin = MibIdentifier((1, 3, 6, 1, 6, 3, 11, 1))
snmpMPDMIBObjects = MibIdentifier((1, 3, 6, 1, 6, 3, 11, 2))
snmpMPDMIBConformance = MibIdentifier((1, 3, 6, 1, 6, 3, 11, 3))
snmpMPDStats = MibIdentifier((1, 3, 6, 1, 6, 3, 11, 2, 1))
snmpUnknownSecurityModels = MibScalar(
    (1, 3, 6, 1, 6, 3, 11, 2, 1, 1), Counter32()
).setMaxAccess("readonly")
if mibBuilder.loadTexts:
    snmpUnknownSecurityModels.setStatus("current")
if mibBuilder.loadTexts:
    snmpUnknownSecurityModels.setDescription(
        "The total number of packets received by the SNMP engine which were dropped because they referenced a securityModel that was not known to or supported by the SNMP engine. "
    )
snmpInvalidMsgs = MibScalar((1, 3, 6, 1, 6, 3, 11, 2, 1, 2), Counter32()).setMaxAccess(
    "readonly"
)
if mibBuilder.loadTexts:
    snmpInvalidMsgs.setStatus("current")
if mibBuilder.loadTexts:
    snmpInvalidMsgs.setDescription(
        "The total number of packets received by the SNMP engine which were dropped because there were invalid or inconsistent components in the SNMP message. "
    )
snmpUnknownPDUHandlers = MibScalar(
    (1, 3, 6, 1, 6, 3, 11, 2, 1, 3), Counter32()
).setMaxAccess("readonly")
if mibBuilder.loadTexts:
    snmpUnknownPDUHandlers.setStatus("current")
if mibBuilder.loadTexts:
    snmpUnknownPDUHandlers.setDescription(
        "The total number of packets received by the SNMP engine which were dropped because the PDU contained in the packet could not be passed to an application responsible for handling the pduType, e.g. no SNMP application had registered for the proper combination of the contextEngineID and the pduType. "
    )
snmpMPDMIBCompliances = MibIdentifier((1, 3, 6, 1, 6, 3, 11, 3, 1))
snmpMPDMIBGroups = MibIdentifier((1, 3, 6, 1, 6, 3, 11, 3, 2))
snmpMPDCompliance = ModuleCompliance((1, 3, 6, 1, 6, 3, 11, 3, 1, 1)).setObjects(
    ("SNMP-MPD-MIB", "snmpMPDGroup")
)

snmpMPDCompliance = snmpMPDCompliance.setStatus("current")
if mibBuilder.loadTexts:
    snmpMPDCompliance.setDescription(
        "The compliance statement for SNMP entities which implement the SNMP-MPD-MIB. "
    )
snmpMPDGroup = ObjectGroup((1, 3, 6, 1, 6, 3, 11, 3, 2, 1)).setObjects(
    ("SNMP-MPD-MIB", "snmpUnknownSecurityModels"),
    ("SNMP-MPD-MIB", "snmpInvalidMsgs"),
    ("SNMP-MPD-MIB", "snmpUnknownPDUHandlers"),
)
snmpMPDGroup = snmpMPDGroup.setStatus("current")
if mibBuilder.loadTexts:
    snmpMPDGroup.setDescription(
        "A collection of objects providing for remote monitoring of the SNMP Message Processing and Dispatching process. "
    )
mibBuilder.exportSymbols(
    "SNMP-MPD-MIB",
    PYSNMP_MODULE_ID=snmpMPDMIB,
    snmpInvalidMsgs=snmpInvalidMsgs,
    snmpMPDAdmin=snmpMPDAdmin,
    snmpMPDCompliance=snmpMPDCompliance,
    snmpMPDGroup=snmpMPDGroup,
    snmpMPDMIB=snmpMPDMIB,
    snmpMPDMIBCompliances=snmpMPDMIBCompliances,
    snmpMPDMIBConformance=snmpMPDMIBConformance,
    snmpMPDMIBGroups=snmpMPDMIBGroups,
    snmpMPDMIBObjects=snmpMPDMIBObjects,
    snmpMPDStats=snmpMPDStats,
    snmpUnknownPDUHandlers=snmpUnknownPDUHandlers,
    snmpUnknownSecurityModels=snmpUnknownSecurityModels,
)
