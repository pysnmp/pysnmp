#
# PySNMP MIB module SNMP-TARGET-MIB (http://snmplabs.com/pysmi)
# ASN.1 source SNMP-TARGET-MIB
# Source digest sha256:39d11d27f1da4e7d6087e0f019e5d82000a28430dba1dc2fa29885c4704af249
# Produced by pysmi-4.0.0-rc.3
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
SnmpAdminString, SnmpMessageProcessingModel, SnmpSecurityLevel, SnmpSecurityModel = (
    mibBuilder.importSymbols(
        "SNMP-FRAMEWORK-MIB",
        "SnmpAdminString",
        "SnmpMessageProcessingModel",
        "SnmpSecurityLevel",
        "SnmpSecurityModel",
    )
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
(
    DisplayString,
    RowStatus,
    StorageType,
    TAddress,
    TDomain,
    TextualConvention,
    TestAndIncr,
    TimeInterval,
) = mibBuilder.importSymbols(
    "SNMPv2-TC",
    "DisplayString",
    "RowStatus",
    "StorageType",
    "TAddress",
    "TDomain",
    "TextualConvention",
    "TestAndIncr",
    "TimeInterval",
)
snmpTargetMIB = ModuleIdentity((1, 3, 6, 1, 6, 3, 12))
snmpTargetMIB.setRevisions(
    (
        "2002-10-14 00:00",
        "1998-08-04 00:00",
        "1997-07-14 00:00",
    )
)
if mibBuilder.loadTexts:
    snmpTargetMIB.setRevisionsDescriptions(
        (
            "Fixed DISPLAY-HINTS for UTF-8 strings, fixed hex value of LF characters, clarified meaning of zero length tag values, improved tag list examples. Published as RFC 3413.",
            "Clarifications, published as RFC 2573.",
            "The initial revision, published as RFC2273.",
        )
    )
if mibBuilder.loadTexts:
    snmpTargetMIB.setLastUpdated("2002-10-14 00:00")
if mibBuilder.loadTexts:
    snmpTargetMIB.setOrganization("IETF SNMPv3 Working Group")
if mibBuilder.loadTexts:
    snmpTargetMIB.setContactInfo(
        "WG-email: snmpv3@lists.tislabs.com Subscribe: majordomo@lists.tislabs.com In message body: subscribe snmpv3 Co-Chair: Russ Mundy Network Associates Laboratories Postal: 15204 Omega Drive, Suite 300 Rockville, MD 20850-4601 USA EMail: mundy@tislabs.com Phone: +1 301-947-7107 Co-Chair: David Harrington Enterasys Networks Postal: 35 Industrial Way P. O. Box 5004 Rochester, New Hampshire 03866-5005 USA EMail: dbh@enterasys.com Phone: +1 603-337-2614 Co-editor: David B. Levi Nortel Networks Postal: 3505 Kesterwood Drive Knoxville, Tennessee 37918 EMail: dlevi@nortelnetworks.com Phone: +1 865 686 0432 Co-editor: Paul Meyer Secure Computing Corporation Postal: 2675 Long Lake Road Roseville, Minnesota 55113 EMail: paul_meyer@securecomputing.com Phone: +1 651 628 1592 Co-editor: Bob Stewart Retired"
    )
if mibBuilder.loadTexts:
    snmpTargetMIB.setDescription(
        "This MIB module defines MIB objects which provide mechanisms to remotely configure the parameters used by an SNMP entity for the generation of SNMP messages. Copyright (C) The Internet Society (2002). This version of this MIB module is part of RFC 3413; see the RFC itself for full legal notices. "
    )
snmpTargetObjects = MibIdentifier((1, 3, 6, 1, 6, 3, 12, 1))
snmpTargetConformance = MibIdentifier((1, 3, 6, 1, 6, 3, 12, 3))


class SnmpTagValue(TextualConvention, OctetString):
    description = "An octet string containing a tag value. Tag values are preferably in human-readable form. To facilitate internationalization, this information is represented using the ISO/IEC IS 10646-1 character set, encoded as an octet string using the UTF-8 character encoding scheme described in RFC 2279. Since additional code points are added by amendments to the 10646 standard from time to time, implementations must be prepared to encounter any code point from 0x00000000 to 0x7fffffff. The use of control codes should be avoided, and certain control codes are not allowed as described below. For code points not directly supported by user interface hardware or software, an alternative means of entry and display, such as hexadecimal, may be provided. For information encoded in 7-bit US-ASCII, the UTF-8 representation is identical to the US-ASCII encoding. Note that when this TC is used for an object that is used or envisioned to be used as an index, then a SIZE restriction must be specified so that the number of sub-identifiers for any object instance does not exceed the limit of 128, as defined by [RFC1905]. An object of this type contains a single tag value which is used to select a set of entries in a table. A tag value is an arbitrary string of octets, but may not contain a delimiter character. Delimiter characters are defined to be one of the following: - An ASCII space character (0x20). - An ASCII TAB character (0x09). - An ASCII carriage return (CR) character (0x0D). - An ASCII line feed (LF) character (0x0A). Delimiter characters are used to separate tag values in a tag list. An object of this type may only contain a single tag value, and so delimiter characters are not allowed in a value of this type. Note that a tag value of 0 length means that no tag is defined. In other words, a tag value of 0 length would never match anything in a tag list, and would never select any table entries. Some examples of valid tag values are: - 'acme' - 'router' - 'host' The use of a tag value to select table entries is application and MIB specific."
    status = "current"
    displayHint = "255t"
    encoding = "utf-8"
    subtypeSpec = OctetString.subtypeSpec + ValueSizeConstraint(0, 255)


class SnmpTagList(TextualConvention, OctetString):
    description = "An octet string containing a list of tag values. Tag values are preferably in human-readable form. To facilitate internationalization, this information is represented using the ISO/IEC IS 10646-1 character set, encoded as an octet string using the UTF-8 character encoding scheme described in RFC 2279. Since additional code points are added by amendments to the 10646 standard from time to time, implementations must be prepared to encounter any code point from 0x00000000 to 0x7fffffff. The use of control codes should be avoided, except as described below. For code points not directly supported by user interface hardware or software, an alternative means of entry and display, such as hexadecimal, may be provided. For information encoded in 7-bit US-ASCII, the UTF-8 representation is identical to the US-ASCII encoding. An object of this type contains a list of tag values which are used to select a set of entries in a table. A tag value is an arbitrary string of octets, but may not contain a delimiter character. Delimiter characters are defined to be one of the following: - An ASCII space character (0x20). - An ASCII TAB character (0x09). - An ASCII carriage return (CR) character (0x0D). - An ASCII line feed (LF) character (0x0A). Delimiter characters are used to separate tag values in a tag list. Only a single delimiter character may occur between two tag values. A tag value may not have a zero length. These constraints imply certain restrictions on the contents of this object: - There cannot be a leading or trailing delimiter character. - There cannot be multiple adjacent delimiter characters. Some examples of valid tag lists are: - '' -- an empty list - 'acme' -- list of one tag - 'host router bridge' -- list of several tags Note that although a tag value may not have a length of zero, an empty string is still valid. This indicates an empty list (i.e. there are no tag values in the list). The use of the tag list to select table entries is application and MIB specific. Typically, an application will provide one or more tag values, and any entry which contains some combination of these tag values will be selected."
    status = "current"
    displayHint = "255t"
    encoding = "utf-8"
    subtypeSpec = OctetString.subtypeSpec + ValueSizeConstraint(0, 255)


snmpTargetSpinLock = MibScalar(
    (1, 3, 6, 1, 6, 3, 12, 1, 1), TestAndIncr()
).setMaxAccess("readwrite")
if mibBuilder.loadTexts:
    snmpTargetSpinLock.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetSpinLock.setDescription(
        "This object is used to facilitate modification of table entries in the SNMP-TARGET-MIB module by multiple managers. In particular, it is useful when modifying the value of the snmpTargetAddrTagList object. The procedure for modifying the snmpTargetAddrTagList object is as follows: 1. Retrieve the value of snmpTargetSpinLock and of snmpTargetAddrTagList. 2. Generate a new value for snmpTargetAddrTagList. 3. Set the value of snmpTargetSpinLock to the retrieved value, and the value of snmpTargetAddrTagList to the new value. If the set fails for the snmpTargetSpinLock object, go back to step 1."
    )
snmpTargetAddrTable = MibTable(
    (1, 3, 6, 1, 6, 3, 12, 1, 2),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    snmpTargetAddrTable.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrTable.setDescription(
        "A table of transport addresses to be used in the generation of SNMP messages."
    )
snmpTargetAddrEntry = (
    MibTableRow(
        (1, 3, 6, 1, 6, 3, 12, 1, 2, 1),
    )
    .setMaxAccess("notaccessible")
    .setIndexNames((1, "SNMP-TARGET-MIB", "snmpTargetAddrName"))
)
if mibBuilder.loadTexts:
    snmpTargetAddrEntry.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrEntry.setDescription(
        "A transport address to be used in the generation of SNMP operations. Entries in the snmpTargetAddrTable are created and deleted using the snmpTargetAddrRowStatus object."
    )
snmpTargetAddrName = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 1),
    SnmpAdminString().subtype(subtypeSpec=ValueSizeConstraint(1, 32)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    snmpTargetAddrName.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrName.setDescription(
        "The locally arbitrary, but unique identifier associated with this snmpTargetAddrEntry."
    )
snmpTargetAddrTDomain = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 2), TDomain()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrTDomain.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrTDomain.setDescription(
        "This object indicates the transport type of the address contained in the snmpTargetAddrTAddress object."
    )
snmpTargetAddrTAddress = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 3), TAddress()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrTAddress.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrTAddress.setDescription(
        "This object contains a transport address. The format of this address depends on the value of the snmpTargetAddrTDomain object."
    )
snmpTargetAddrTimeout = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 4), TimeInterval().clone(1500)
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrTimeout.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrTimeout.setDescription(
        "This object should reflect the expected maximum round trip time for communicating with the transport address defined by this row. When a message is sent to this address, and a response (if one is expected) is not received within this time period, an implementation may assume that the response will not be delivered. Note that the time interval that an application waits for a response may actually be derived from the value of this object. The method for deriving the actual time interval is implementation dependent. One such method is to derive the expected round trip time based on a particular retransmission algorithm and on the number of timeouts which have occurred. The type of message may also be considered when deriving expected round trip times for retransmissions. For example, if a message is being sent with a securityLevel that indicates both authentication and privacy, the derived value may be increased to compensate for extra processing time spent during authentication and encryption processing."
    )
snmpTargetAddrRetryCount = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 5),
    Integer32().subtype(subtypeSpec=ValueRangeConstraint(0, 255)).clone(3),
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrRetryCount.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrRetryCount.setDescription(
        "This object specifies a default number of retries to be attempted when a response is not received for a generated message. An application may provide its own retry count, in which case the value of this object is ignored."
    )
snmpTargetAddrTagList = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 6), SnmpTagList().clone("")
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrTagList.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrTagList.setDescription(
        "This object contains a list of tag values which are used to select target addresses for a particular operation."
    )
snmpTargetAddrParams = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 7),
    SnmpAdminString().subtype(subtypeSpec=ValueSizeConstraint(1, 32)),
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrParams.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrParams.setDescription(
        "The value of this object identifies an entry in the snmpTargetParamsTable. The identified entry contains SNMP parameters to be used when generating messages to be sent to this transport address."
    )
snmpTargetAddrStorageType = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 8), StorageType().clone("nonVolatile")
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrStorageType.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrStorageType.setDescription(
        "The storage type for this conceptual row. Conceptual rows having the value 'permanent' need not allow write-access to any columnar objects in the row."
    )
snmpTargetAddrRowStatus = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 2, 1, 9), RowStatus()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetAddrRowStatus.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetAddrRowStatus.setDescription(
        "The status of this conceptual row. To create a row in this table, a manager must set this object to either createAndGo(4) or createAndWait(5). Until instances of all corresponding columns are appropriately configured, the value of the corresponding instance of the snmpTargetAddrRowStatus column is 'notReady'. In particular, a newly created row cannot be made active until the corresponding instances of snmpTargetAddrTDomain, snmpTargetAddrTAddress, and snmpTargetAddrParams have all been set. The following objects may not be modified while the value of this object is active(1): - snmpTargetAddrTDomain - snmpTargetAddrTAddress An attempt to set these objects while the value of snmpTargetAddrRowStatus is active(1) will result in an inconsistentValue error."
    )
snmpTargetParamsTable = MibTable(
    (1, 3, 6, 1, 6, 3, 12, 1, 3),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    snmpTargetParamsTable.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsTable.setDescription(
        "A table of SNMP target information to be used in the generation of SNMP messages."
    )
snmpTargetParamsEntry = (
    MibTableRow(
        (1, 3, 6, 1, 6, 3, 12, 1, 3, 1),
    )
    .setMaxAccess("notaccessible")
    .setIndexNames((1, "SNMP-TARGET-MIB", "snmpTargetParamsName"))
)
if mibBuilder.loadTexts:
    snmpTargetParamsEntry.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsEntry.setDescription(
        "A set of SNMP target information. Entries in the snmpTargetParamsTable are created and deleted using the snmpTargetParamsRowStatus object."
    )
snmpTargetParamsName = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 3, 1, 1),
    SnmpAdminString().subtype(subtypeSpec=ValueSizeConstraint(1, 32)),
).setMaxAccess("notaccessible")
if mibBuilder.loadTexts:
    snmpTargetParamsName.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsName.setDescription(
        "The locally arbitrary, but unique identifier associated with this snmpTargetParamsEntry."
    )
snmpTargetParamsMPModel = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 3, 1, 2), SnmpMessageProcessingModel()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetParamsMPModel.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsMPModel.setDescription(
        "The Message Processing Model to be used when generating SNMP messages using this entry."
    )
snmpTargetParamsSecurityModel = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 3, 1, 3),
    SnmpSecurityModel().subtype(subtypeSpec=ValueRangeConstraint(1, 2147483647)),
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetParamsSecurityModel.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsSecurityModel.setDescription(
        "The Security Model to be used when generating SNMP messages using this entry. An implementation may choose to return an inconsistentValue error if an attempt is made to set this variable to a value for a security model which the implementation does not support."
    )
snmpTargetParamsSecurityName = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 3, 1, 4), SnmpAdminString()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetParamsSecurityName.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsSecurityName.setDescription(
        "The securityName which identifies the Principal on whose behalf SNMP messages will be generated using this entry."
    )
snmpTargetParamsSecurityLevel = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 3, 1, 5), SnmpSecurityLevel()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetParamsSecurityLevel.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsSecurityLevel.setDescription(
        "The Level of Security to be used when generating SNMP messages using this entry."
    )
snmpTargetParamsStorageType = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 3, 1, 6), StorageType().clone("nonVolatile")
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetParamsStorageType.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsStorageType.setDescription(
        "The storage type for this conceptual row. Conceptual rows having the value 'permanent' need not allow write-access to any columnar objects in the row."
    )
snmpTargetParamsRowStatus = MibTableColumn(
    (1, 3, 6, 1, 6, 3, 12, 1, 3, 1, 7), RowStatus()
).setMaxAccess("readcreate")
if mibBuilder.loadTexts:
    snmpTargetParamsRowStatus.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetParamsRowStatus.setDescription(
        "The status of this conceptual row. To create a row in this table, a manager must set this object to either createAndGo(4) or createAndWait(5). Until instances of all corresponding columns are appropriately configured, the value of the corresponding instance of the snmpTargetParamsRowStatus column is 'notReady'. In particular, a newly created row cannot be made active until the corresponding snmpTargetParamsMPModel, snmpTargetParamsSecurityModel, snmpTargetParamsSecurityName, and snmpTargetParamsSecurityLevel have all been set. The following objects may not be modified while the value of this object is active(1): - snmpTargetParamsMPModel - snmpTargetParamsSecurityModel - snmpTargetParamsSecurityName - snmpTargetParamsSecurityLevel An attempt to set these objects while the value of snmpTargetParamsRowStatus is active(1) will result in an inconsistentValue error."
    )
snmpUnavailableContexts = MibScalar(
    (1, 3, 6, 1, 6, 3, 12, 1, 4), Counter32()
).setMaxAccess("readonly")
if mibBuilder.loadTexts:
    snmpUnavailableContexts.setStatus("current")
if mibBuilder.loadTexts:
    snmpUnavailableContexts.setDescription(
        "The total number of packets received by the SNMP engine which were dropped because the context contained in the message was unavailable."
    )
snmpUnknownContexts = MibScalar((1, 3, 6, 1, 6, 3, 12, 1, 5), Counter32()).setMaxAccess(
    "readonly"
)
if mibBuilder.loadTexts:
    snmpUnknownContexts.setStatus("current")
if mibBuilder.loadTexts:
    snmpUnknownContexts.setDescription(
        "The total number of packets received by the SNMP engine which were dropped because the context contained in the message was unknown."
    )
snmpTargetCompliances = MibIdentifier((1, 3, 6, 1, 6, 3, 12, 3, 1))
snmpTargetGroups = MibIdentifier((1, 3, 6, 1, 6, 3, 12, 3, 2))
snmpTargetCommandResponderCompliance = ModuleCompliance(
    (1, 3, 6, 1, 6, 3, 12, 3, 1, 1)
).setObjects(("SNMP-TARGET-MIB", "snmpTargetCommandResponderGroup"))

snmpTargetCommandResponderCompliance = snmpTargetCommandResponderCompliance.setStatus(
    "current"
)
if mibBuilder.loadTexts:
    snmpTargetCommandResponderCompliance.setDescription(
        "The compliance statement for SNMP entities which include a command responder application."
    )
snmpTargetBasicGroup = ObjectGroup((1, 3, 6, 1, 6, 3, 12, 3, 2, 1)).setObjects(
    ("SNMP-TARGET-MIB", "snmpTargetSpinLock"),
    ("SNMP-TARGET-MIB", "snmpTargetAddrTDomain"),
    ("SNMP-TARGET-MIB", "snmpTargetAddrTAddress"),
    ("SNMP-TARGET-MIB", "snmpTargetAddrTagList"),
    ("SNMP-TARGET-MIB", "snmpTargetAddrParams"),
    ("SNMP-TARGET-MIB", "snmpTargetAddrStorageType"),
    ("SNMP-TARGET-MIB", "snmpTargetAddrRowStatus"),
    ("SNMP-TARGET-MIB", "snmpTargetParamsMPModel"),
    ("SNMP-TARGET-MIB", "snmpTargetParamsSecurityModel"),
    ("SNMP-TARGET-MIB", "snmpTargetParamsSecurityName"),
    ("SNMP-TARGET-MIB", "snmpTargetParamsSecurityLevel"),
    ("SNMP-TARGET-MIB", "snmpTargetParamsStorageType"),
    ("SNMP-TARGET-MIB", "snmpTargetParamsRowStatus"),
)
snmpTargetBasicGroup = snmpTargetBasicGroup.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetBasicGroup.setDescription(
        "A collection of objects providing basic remote configuration of management targets."
    )
snmpTargetResponseGroup = ObjectGroup((1, 3, 6, 1, 6, 3, 12, 3, 2, 2)).setObjects(
    ("SNMP-TARGET-MIB", "snmpTargetAddrTimeout"),
    ("SNMP-TARGET-MIB", "snmpTargetAddrRetryCount"),
)
snmpTargetResponseGroup = snmpTargetResponseGroup.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetResponseGroup.setDescription(
        "A collection of objects providing remote configuration of management targets for applications which generate SNMP messages for which a response message would be expected."
    )
snmpTargetCommandResponderGroup = ObjectGroup(
    (1, 3, 6, 1, 6, 3, 12, 3, 2, 3)
).setObjects(
    ("SNMP-TARGET-MIB", "snmpUnavailableContexts"),
    ("SNMP-TARGET-MIB", "snmpUnknownContexts"),
)
snmpTargetCommandResponderGroup = snmpTargetCommandResponderGroup.setStatus("current")
if mibBuilder.loadTexts:
    snmpTargetCommandResponderGroup.setDescription(
        "A collection of objects required for command responder applications, used for counting error conditions."
    )
mibBuilder.exportSymbols(
    "SNMP-TARGET-MIB",
    PYSNMP_MODULE_ID=snmpTargetMIB,
    SnmpTagList=SnmpTagList,
    SnmpTagValue=SnmpTagValue,
    snmpTargetAddrEntry=snmpTargetAddrEntry,
    snmpTargetAddrName=snmpTargetAddrName,
    snmpTargetAddrParams=snmpTargetAddrParams,
    snmpTargetAddrRetryCount=snmpTargetAddrRetryCount,
    snmpTargetAddrRowStatus=snmpTargetAddrRowStatus,
    snmpTargetAddrStorageType=snmpTargetAddrStorageType,
    snmpTargetAddrTAddress=snmpTargetAddrTAddress,
    snmpTargetAddrTDomain=snmpTargetAddrTDomain,
    snmpTargetAddrTable=snmpTargetAddrTable,
    snmpTargetAddrTagList=snmpTargetAddrTagList,
    snmpTargetAddrTimeout=snmpTargetAddrTimeout,
    snmpTargetBasicGroup=snmpTargetBasicGroup,
    snmpTargetCommandResponderCompliance=snmpTargetCommandResponderCompliance,
    snmpTargetCommandResponderGroup=snmpTargetCommandResponderGroup,
    snmpTargetCompliances=snmpTargetCompliances,
    snmpTargetConformance=snmpTargetConformance,
    snmpTargetGroups=snmpTargetGroups,
    snmpTargetMIB=snmpTargetMIB,
    snmpTargetObjects=snmpTargetObjects,
    snmpTargetParamsEntry=snmpTargetParamsEntry,
    snmpTargetParamsMPModel=snmpTargetParamsMPModel,
    snmpTargetParamsName=snmpTargetParamsName,
    snmpTargetParamsRowStatus=snmpTargetParamsRowStatus,
    snmpTargetParamsSecurityLevel=snmpTargetParamsSecurityLevel,
    snmpTargetParamsSecurityModel=snmpTargetParamsSecurityModel,
    snmpTargetParamsSecurityName=snmpTargetParamsSecurityName,
    snmpTargetParamsStorageType=snmpTargetParamsStorageType,
    snmpTargetParamsTable=snmpTargetParamsTable,
    snmpTargetResponseGroup=snmpTargetResponseGroup,
    snmpTargetSpinLock=snmpTargetSpinLock,
    snmpUnavailableContexts=snmpUnavailableContexts,
    snmpUnknownContexts=snmpUnknownContexts,
)
