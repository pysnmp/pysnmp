#
# PySNMP MIB module PYSNMP-MIB (http://snmplabs.com/pysmi)
# ASN.1 source PYSNMP-MIB.txt
# Source digest sha256:45033dc08c328f8c3f7f4ccb13bfa26b06a813301c75fe87e2ba7fcb1debfc83
# Produced by pysmi-4.0.0-rc.2
#
PYSNMP_MODULE_REVISION = "201704140000Z"

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
    enterprises,
    iso,
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
    "enterprises",
    "iso",
)
DisplayString, TextualConvention = mibBuilder.importSymbols(
    "SNMPv2-TC", "DisplayString", "TextualConvention"
)
pysnmp = ModuleIdentity((1, 3, 6, 1, 4, 1, 20408))
pysnmp.setRevisions(
    (
        "2017-04-14 00:00",
        "2005-05-14 00:00",
    )
)
if mibBuilder.loadTexts:
    pysnmp.setRevisionsDescriptions(
        (
            "Updated addresses",
            "Initial revision",
        )
    )
if mibBuilder.loadTexts:
    pysnmp.setLastUpdated("2017-04-14 00:00")
if mibBuilder.loadTexts:
    pysnmp.setOrganization("The PySNMP Project")
if mibBuilder.loadTexts:
    pysnmp.setContactInfo(
        "E-mail: Ilya Etingof deceased GitHub: https://github.com/etingof/pysnmp"
    )
if mibBuilder.loadTexts:
    pysnmp.setDescription("PySNMP top-level MIB tree infrastructure")
pysnmpObjects = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 1))
pysnmpExamples = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 2))
pysnmpEnumerations = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3))
pysnmpModuleIDs = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1))
pysnmpAgentOIDs = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 2))
pysnmpDomains = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 3))
pysnmpExperimental = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 9999))
pysnmpNotificationPrefix = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 4))
pysnmpNotifications = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 4, 0))
pysnmpNotificationObjects = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 4, 1))
pysnmpConformance = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 5))
pysnmpCompliances = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 5, 1))
pysnmpGroups = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 5, 2))
mibBuilder.exportSymbols(
    "PYSNMP-MIB",
    PYSNMP_MODULE_ID=pysnmp,
    pysnmp=pysnmp,
    pysnmpAgentOIDs=pysnmpAgentOIDs,
    pysnmpCompliances=pysnmpCompliances,
    pysnmpConformance=pysnmpConformance,
    pysnmpDomains=pysnmpDomains,
    pysnmpEnumerations=pysnmpEnumerations,
    pysnmpExamples=pysnmpExamples,
    pysnmpExperimental=pysnmpExperimental,
    pysnmpGroups=pysnmpGroups,
    pysnmpModuleIDs=pysnmpModuleIDs,
    pysnmpNotificationObjects=pysnmpNotificationObjects,
    pysnmpNotificationPrefix=pysnmpNotificationPrefix,
    pysnmpNotifications=pysnmpNotifications,
    pysnmpObjects=pysnmpObjects,
)
