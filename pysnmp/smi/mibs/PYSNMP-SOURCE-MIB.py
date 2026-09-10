#
# PySNMP MIB module PYSNMP-SOURCE-MIB (http://snmplabs.com/pysmi)
# ASN.1 source PYSNMP-SOURCE-MIB.txt
# Source digest sha256:8196d30b7c7197db3aeb5eb58b52b72679ad102176a1ce4dcf97762cd00874f5
# Produced by pysmi-4.0.0-rc.4
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
(snmpTargetAddrEntry,) = mibBuilder.importSymbols(
    "SNMP-TARGET-MIB", "snmpTargetAddrEntry"
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
DisplayString, TAddress, TextualConvention = mibBuilder.importSymbols(
    "SNMPv2-TC", "DisplayString", "TAddress", "TextualConvention"
)
pysnmpSourceMIB = ModuleIdentity((1, 3, 6, 1, 4, 1, 20408, 3, 1, 8))
pysnmpSourceMIB.setRevisions(
    (
        "2017-04-14 00:00",
        "2015-01-16 00:00",
    )
)
if mibBuilder.loadTexts:
    pysnmpSourceMIB.setRevisionsDescriptions(
        (
            "Updated addresses",
            "Initial Revision",
        )
    )
if mibBuilder.loadTexts:
    pysnmpSourceMIB.setLastUpdated("2017-04-14 00:00")
if mibBuilder.loadTexts:
    pysnmpSourceMIB.setOrganization("The PySNMP Project")
if mibBuilder.loadTexts:
    pysnmpSourceMIB.setContactInfo(
        "E-mail: Ilya Etingof deceased GitHub: https://github.com/etingof/pysnmp"
    )
if mibBuilder.loadTexts:
    pysnmpSourceMIB.setDescription(
        "This MIB module defines implementation specific objects that provide variable source transport endpoints feature to SNMP Engine and Standard SNMP Applications."
    )
pysnmpSourceMIBObjects = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 8, 1))
pysnmpSourceMIBConformance = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 8, 2))
snmpSourceAddrTable = MibTable(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 8, 1, 1),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    snmpSourceAddrTable.setStatus("current")
if mibBuilder.loadTexts:
    snmpSourceAddrTable.setDescription(
        "A table of transport addresses to be used as a source in the generation of SNMP messages. This table contains additional objects for the SNMP-TRANSPORT-ADDRESS::snmpSourceAddressTable."
    )
snmpSourceAddrEntry = MibTableRow(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 8, 1, 1, 1),
).setMaxAccess("notaccessible")
snmpTargetAddrEntry.registerAugmentions(("PYSNMP-SOURCE-MIB", "snmpSourceAddrEntry"))
snmpSourceAddrEntry.setIndexNames(*snmpTargetAddrEntry.getIndexNames())
if mibBuilder.loadTexts:
    snmpSourceAddrEntry.setStatus("current")
if mibBuilder.loadTexts:
    snmpSourceAddrEntry.setDescription(
        "A transport address to be used as a source in the generation of SNMP operations. An entry containing additional management information applicable to a particular target."
    )
snmpSourceAddrTAddress = MibTableColumn(
    (1, 3, 6, 1, 4, 1, 20408, 3, 1, 8, 1, 1, 1, 1), TAddress()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpSourceAddrTAddress.setStatus("current")
if mibBuilder.loadTexts:
    snmpSourceAddrTAddress.setDescription(
        "This object contains a transport address. The format of this address depends on the value of the snmpSourceAddrTDomain object."
    )
pysnmpSourceMIBCompliances = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 8, 2, 1))
pysnmpSourceMIBGroups = MibIdentifier((1, 3, 6, 1, 4, 1, 20408, 3, 1, 8, 2, 2))
mibBuilder.exportSymbols(
    "PYSNMP-SOURCE-MIB",
    PYSNMP_MODULE_ID=pysnmpSourceMIB,
    pysnmpSourceMIB=pysnmpSourceMIB,
    pysnmpSourceMIBCompliances=pysnmpSourceMIBCompliances,
    pysnmpSourceMIBConformance=pysnmpSourceMIBConformance,
    pysnmpSourceMIBGroups=pysnmpSourceMIBGroups,
    pysnmpSourceMIBObjects=pysnmpSourceMIBObjects,
    snmpSourceAddrEntry=snmpSourceAddrEntry,
    snmpSourceAddrTAddress=snmpSourceAddrTAddress,
    snmpSourceAddrTable=snmpSourceAddrTable,
)
