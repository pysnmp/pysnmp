#
# PySNMP MIB module PYSNMP-USM-MIB (http://snmplabs.com/pysmi)
# ASN.1 source PYSNMP-USM-MIB.txt
# Source digest sha256:7789d11fb75f3c642f1397ea491949c5a88b5a93fe3286fa7b414720929ec16d
# Produced by pysmi-4.0.0-rc.3
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
(pysnmpModuleIDs,) = mibBuilder.importSymbols("PYSNMP-MIB", "pysnmpModuleIDs")
(SnmpAdminString,) = mibBuilder.importSymbols("SNMP-FRAMEWORK-MIB", "SnmpAdminString")
(usmUserEntry,) = mibBuilder.importSymbols("SNMP-USER-BASED-SM-MIB", "usmUserEntry")
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
)
DisplayString, RowStatus, TextualConvention = mibBuilder.importSymbols(
    "SNMPv2-TC", "DisplayString", "RowStatus", "TextualConvention"
)
pysnmpUsmMIB = ModuleIdentity((1, 3, 6, 1, 4, 1, 20408, 3, 1, 1))
pysnmpUsmMIB.setRevisions(
    (
        "2019-08-30 00:00",
        "2017-07-30 00:00",
        "2017-04-14 00:00",
        "2005-05-14 00:00",
    )
)
if mibBuilder.loadTexts:
    pysnmpUsmMIB.setRevisionsDescriptions(
        (
            "Added USM key types",
            "Extended authentication key size",
            "Updated addresses",
            "The Initial Revision",
        )
    )
if mibBuilder.loadTexts:
    pysnmpUsmMIB.setLastUpdated("2017-04-14 00:00")
if mibBuilder.loadTexts:
    pysnmpUsmMIB.setOrganization("The PySNMP Project")
if mibBuilder.loadTexts:
    pysnmpUsmMIB.setContactInfo(
        "E-mail: Ilya Etingof deceased GitHub: https://github.com/etingof/pysnmp"
    )
if mibBuilder.loadTexts:
    pysnmpUsmMIB.setDescription(
        "This MIB module defines objects specific to User Security Model (USM) implementation at PySNMP."
    )
pysnmpUsmMIBObjects = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1))
pysnmpUsmMIBConformance = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 2))
pysnmpUsmCfg = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 1))
pysnmpUsmDiscoverable = MibScalar(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 1, 1),
    Integer32()
    .subtype(subtypeSpec=ConstraintsUnion(SingleValueConstraint(0, 1)))
    .clone(namedValues=NamedValues(("notDiscoverable", 0), ("discoverable", 1)))
    .clone("discoverable"),
).setMaxAccess("readwrite")
if mibBuilder.loadTexts:
    pysnmpUsmDiscoverable.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmDiscoverable.setDescription(
        "Whether SNMP engine would support its discovery by responding to unknown clients."
    )
pysnmpUsmDiscovery = MibScalar(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 1, 2),
    Integer32()
    .subtype(subtypeSpec=ConstraintsUnion(SingleValueConstraint(0, 1)))
    .clone(namedValues=NamedValues(("doNotDiscover", 0), ("doDiscover", 1)))
    .clone("doDiscover"),
).setMaxAccess("readwrite")
if mibBuilder.loadTexts:
    pysnmpUsmDiscovery.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmDiscovery.setDescription(
        "Whether SNMP engine would try to figure out the EngineIDs of its peers by sending discover requests."
    )
pysnmpUsmKeyType = MibScalar(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 1, 3),
    Integer32()
    .subtype(subtypeSpec=ConstraintsUnion(SingleValueConstraint(0, 1, 2)))
    .clone(namedValues=NamedValues(("passphrase", 0), ("master", 1), ("localized", 2)))
    .clone("passphrase"),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmKeyType.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmKeyType.setDescription(
        "When configuring USM user, the value of this enumeration determines how the keys should be treated. The default value 'passphrase' means that given keys are plain-text pass-phrases, 'master' indicates that the keys are pre-hashed pass-phrases, while 'localized' stands for pre-hashed pass-phrases mixed with SNMP Security Engine ID value."
    )
pysnmpUsmUser = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 3))
pysnmpUsmSecretTable = MibTable(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 2),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmSecretTable.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmSecretTable.setDescription(
        "The table of USM users passphrases configured in the SNMP engine's Local Configuration Datastore (LCD)."
    )
pysnmpUsmSecretEntry = (
    MibTableRow(
        (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 2, 1),
    )
    .setMaxAccess("notaccessible")
    .setIndexNames((1, "PYSNMP-USM-MIB", "pysnmpUsmSecretUserName"))
)
if mibBuilder.loadTexts:
    pysnmpUsmSecretEntry.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmSecretEntry.setDescription(
        "Information about a particular USM user credentials."
    )
pysnmpUsmSecretUserName = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 2, 1, 1),
    SnmpAdminString().subtype(subtypeSpec=ValueSizeConstraint(1, 32)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmSecretUserName.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmSecretUserName.setDescription(
        "The username string for which a row in this table represents a configuration."
    )
pysnmpUsmSecretAuthKey = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 2, 1, 2),
    OctetString().subtype(subtypeSpec=ValueSizeConstraint(8, 65535)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmSecretAuthKey.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmSecretAuthKey.setDescription(
        "User's authentication passphrase used for localized key generation."
    )
pysnmpUsmSecretPrivKey = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 2, 1, 3),
    OctetString().subtype(subtypeSpec=ValueSizeConstraint(8, 65535)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmSecretPrivKey.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmSecretPrivKey.setDescription(
        "User's encryption passphrase used for localized key generation."
    )
pysnmpUsmSecretStatus = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 2, 1, 4), RowStatus()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    pysnmpUsmSecretStatus.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmSecretStatus.setDescription("Table status")
pysnmpUsmKeyTable = MibTable(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 3),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmKeyTable.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmKeyTable.setDescription(
        "The table of USM users localized keys configured in the SNMP engine's Local Configuration Datastore (LCD)."
    )
pysnmpUsmKeyEntry = MibTableRow(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 3, 1),
).setMaxAccess("notaccessible")
usmUserEntry.registerAugmentions(("PYSNMP-USM-MIB", "pysnmpUsmKeyEntry"))
pysnmpUsmKeyEntry.setIndexNames(*usmUserEntry.getIndexNames())
if mibBuilder.loadTexts:
    pysnmpUsmKeyEntry.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmKeyEntry.setDescription(
        "Information about a particular USM user credentials."
    )
pysnmpUsmKeyAuthLocalized = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 3, 1, 1),
    OctetString().subtype(subtypeSpec=ValueSizeConstraint(8, 64)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmKeyAuthLocalized.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmKeyAuthLocalized.setDescription(
        "User's localized key used for authentication."
    )
pysnmpUsmKeyPrivLocalized = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 3, 1, 2),
    OctetString().subtype(subtypeSpec=ValueSizeConstraint(8, 64)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmKeyPrivLocalized.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmKeyPrivLocalized.setDescription(
        "User's localized key used for encryption."
    )
pysnmpUsmKeyAuth = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 3, 1, 3),
    OctetString().subtype(subtypeSpec=ValueSizeConstraint(8, 64)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmKeyAuth.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmKeyAuth.setDescription("User's non-localized key used for authentication.")
pysnmpUsmKeyPriv = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 1, 3, 1, 4),
    OctetString().subtype(subtypeSpec=ValueSizeConstraint(8, 64)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    pysnmpUsmKeyPriv.setStatus("current")
if mibBuilder.loadTexts:
    pysnmpUsmKeyPriv.setDescription("User's non-localized key used for encryption.")
pysnmpUsmMIBCompliances = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 2, 1))
pysnmpUsmMIBGroups = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 1, 2, 2))
mibBuilder.exportSymbols(
    "PYSNMP-USM-MIB",
    PYSNMP_MODULE_ID=pysnmpUsmMIB,
    pysnmpUsmCfg=pysnmpUsmCfg,
    pysnmpUsmDiscoverable=pysnmpUsmDiscoverable,
    pysnmpUsmDiscovery=pysnmpUsmDiscovery,
    pysnmpUsmKeyAuth=pysnmpUsmKeyAuth,
    pysnmpUsmKeyAuthLocalized=pysnmpUsmKeyAuthLocalized,
    pysnmpUsmKeyEntry=pysnmpUsmKeyEntry,
    pysnmpUsmKeyPriv=pysnmpUsmKeyPriv,
    pysnmpUsmKeyPrivLocalized=pysnmpUsmKeyPrivLocalized,
    pysnmpUsmKeyTable=pysnmpUsmKeyTable,
    pysnmpUsmKeyType=pysnmpUsmKeyType,
    pysnmpUsmMIB=pysnmpUsmMIB,
    pysnmpUsmMIBCompliances=pysnmpUsmMIBCompliances,
    pysnmpUsmMIBConformance=pysnmpUsmMIBConformance,
    pysnmpUsmMIBGroups=pysnmpUsmMIBGroups,
    pysnmpUsmMIBObjects=pysnmpUsmMIBObjects,
    pysnmpUsmSecretAuthKey=pysnmpUsmSecretAuthKey,
    pysnmpUsmSecretEntry=pysnmpUsmSecretEntry,
    pysnmpUsmSecretPrivKey=pysnmpUsmSecretPrivKey,
    pysnmpUsmSecretStatus=pysnmpUsmSecretStatus,
    pysnmpUsmSecretTable=pysnmpUsmSecretTable,
    pysnmpUsmSecretUserName=pysnmpUsmSecretUserName,
    pysnmpUsmUser=pysnmpUsmUser,
)
