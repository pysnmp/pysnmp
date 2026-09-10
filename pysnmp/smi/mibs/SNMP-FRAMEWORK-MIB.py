#
# PySNMP MIB module SNMP-FRAMEWORK-MIB (http://snmplabs.com/pysmi)
# ASN.1 source SNMP-FRAMEWORK-MIB
# Source digest sha256:8e097e7b3fae34f5767a7b7d8ecb7f5765921642b08ec3c62cd8e1f30ef27f42
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
snmpFrameworkMIB = ModuleIdentity((1, 3, 6, 1, 6, 3, 10))
snmpFrameworkMIB.setRevisions(
    (
        "2002-10-14 00:00",
        "1999-01-19 00:00",
        "1997-11-20 00:00",
    )
)
if mibBuilder.loadTexts:
    snmpFrameworkMIB.setRevisionsDescriptions(
        (
            "Changes in this revision: - Updated various administrative information. - Corrected some typos. - Corrected typo in description of SnmpEngineID that led to range overlap for 127. - Changed '255a' to '255t' in definition of SnmpAdminString to align with current SMI. - Reworded 'reserved' for value zero in DESCRIPTION of SnmpSecurityModel. - The algorithm for allocating security models should give 256 per enterprise block, rather than 255. - The example engine ID of 'abcd' is not legal. Replaced with '800002b804616263'H based on example enterprise 696, string 'abc'. - Added clarification that engineID should persist across re-initializations. This revision published as RFC 3411. ",
            "Updated editors' addresses, fixed typos. Published as RFC 2571. ",
            "The initial version, published in RFC 2271. ",
        )
    )
if mibBuilder.loadTexts:
    snmpFrameworkMIB.setLastUpdated("2002-10-14 00:00")
if mibBuilder.loadTexts:
    snmpFrameworkMIB.setOrganization("SNMPv3 Working Group")
if mibBuilder.loadTexts:
    snmpFrameworkMIB.setContactInfo(
        "WG-EMail: snmpv3@lists.tislabs.com Subscribe: snmpv3-request@lists.tislabs.com Co-Chair: Russ Mundy Network Associates Laboratories postal: 15204 Omega Drive, Suite 300 Rockville, MD 20850-4601 USA EMail: mundy@tislabs.com phone: +1 301-947-7107 Co-Chair & Co-editor: David Harrington Enterasys Networks postal: 35 Industrial Way P. O. Box 5005 Rochester, New Hampshire 03866-5005 USA EMail: dbh@enterasys.com phone: +1 603-337-2614 Co-editor: Randy Presuhn BMC Software, Inc. postal: 2141 North First Street San Jose, California 95131 USA EMail: randy_presuhn@bmc.com phone: +1 408-546-1006 Co-editor: Bert Wijnen Lucent Technologies postal: Schagen 33 3461 GL Linschoten Netherlands EMail: bwijnen@lucent.com phone: +31 348-680-485 "
    )
if mibBuilder.loadTexts:
    snmpFrameworkMIB.setDescription(
        "The SNMP Management Architecture MIB Copyright (C) The Internet Society (2002). This version of this MIB module is part of RFC 3411; see the RFC itself for full legal notices. "
    )


class SnmpEngineID(TextualConvention, OctetString):
    description = "An SNMP engine's administratively-unique identifier. Objects of this type are for identification, not for addressing, even though it is possible that an address may have been used in the generation of a specific value. The value for this object may not be all zeros or all 'ff'H or the empty (zero length) string. The initial value for this object may be configured via an operator console entry or via an algorithmic function. In the latter case, the following example algorithm is recommended. In cases where there are multiple engines on the same system, the use of this algorithm is NOT appropriate, as it would result in all of those engines ending up with the same ID value. 1) The very first bit is used to indicate how the rest of the data is composed. 0 - as defined by enterprise using former methods that existed before SNMPv3. See item 2 below. 1 - as defined by this architecture, see item 3 below. Note that this allows existing uses of the engineID (also known as AgentID [RFC1910]) to co-exist with any new uses. 2) The snmpEngineID has a length of 12 octets. The first four octets are set to the binary equivalent of the agent's SNMP management private enterprise number as assigned by the Internet Assigned Numbers Authority (IANA). For example, if Acme Networks has been assigned { enterprises 696 }, the first four octets would be assigned '000002b8'H. The remaining eight octets are determined via one or more enterprise-specific methods. Such methods must be designed so as to maximize the possibility that the value of this object will be unique in the agent's administrative domain. For example, it may be the IP address of the SNMP entity, or the MAC address of one of the interfaces, with each address suitably padded with random octets. If multiple methods are defined, then it is recommended that the first octet indicate the method being used and the remaining octets be a function of the method. 3) The length of the octet string varies. The first four octets are set to the binary equivalent of the agent's SNMP management private enterprise number as assigned by the Internet Assigned Numbers Authority (IANA). For example, if Acme Networks has been assigned { enterprises 696 }, the first four octets would be assigned '000002b8'H. The very first bit is set to 1. For example, the above value for Acme Networks now changes to be '800002b8'H. The fifth octet indicates how the rest (6th and following octets) are formatted. The values for the fifth octet are: 0 - reserved, unused. 1 - IPv4 address (4 octets) lowest non-special IP address 2 - IPv6 address (16 octets) lowest non-special IP address 3 - MAC address (6 octets) lowest IEEE MAC address, canonical order 4 - Text, administratively assigned Maximum remaining length 27 5 - Octets, administratively assigned Maximum remaining length 27 6-127 - reserved, unused 128-255 - as defined by the enterprise Maximum remaining length 27 "
    status = "current"
    subtypeSpec = OctetString.subtypeSpec + ValueSizeConstraint(5, 32)


class SnmpSecurityModel(TextualConvention, Integer32):
    description = "An identifier that uniquely identifies a Security Model of the Security Subsystem within this SNMP Management Architecture. The values for securityModel are allocated as follows: - The zero value does not identify any particular security model. - Values between 1 and 255, inclusive, are reserved for standards-track Security Models and are managed by the Internet Assigned Numbers Authority (IANA). - Values greater than 255 are allocated to enterprise-specific Security Models. An enterprise-specific securityModel value is defined to be: enterpriseID * 256 + security model within enterprise For example, the fourth Security Model defined by the enterprise whose enterpriseID is 1 would be 259. This scheme for allocation of securityModel values allows for a maximum of 255 standards- based Security Models, and for a maximum of 256 Security Models per enterprise. It is believed that the assignment of new securityModel values will be rare in practice because the larger the number of simultaneously utilized Security Models, the larger the chance that interoperability will suffer. Consequently, it is believed that such a range will be sufficient. In the unlikely event that the standards committee finds this number to be insufficient over time, an enterprise number can be allocated to obtain an additional 256 possible values. Note that the most significant bit must be zero; hence, there are 23 bits allocated for various organizations to design and define non-standard securityModels. This limits the ability to define new proprietary implementations of Security Models to the first 8,388,608 enterprises. It is worthwhile to note that, in its encoded form, the securityModel value will normally require only a single byte since, in practice, the leftmost bits will be zero for most messages and sign extension is suppressed by the encoding rules. As of this writing, there are several values of securityModel defined for use with SNMP or reserved for use with supporting MIB objects. They are as follows: 0 reserved for 'any' 1 reserved for SNMPv1 2 reserved for SNMPv2c 3 User-Based Security Model (USM) "
    status = "current"
    subtypeSpec = Integer32.subtypeSpec + ValueRangeConstraint(0, 2147483647)


class SnmpMessageProcessingModel(TextualConvention, Integer32):
    description = "An identifier that uniquely identifies a Message Processing Model of the Message Processing Subsystem within this SNMP Management Architecture. The values for messageProcessingModel are allocated as follows: - Values between 0 and 255, inclusive, are reserved for standards-track Message Processing Models and are managed by the Internet Assigned Numbers Authority (IANA). - Values greater than 255 are allocated to enterprise-specific Message Processing Models. An enterprise messageProcessingModel value is defined to be: enterpriseID * 256 + messageProcessingModel within enterprise For example, the fourth Message Processing Model defined by the enterprise whose enterpriseID is 1 would be 259. This scheme for allocating messageProcessingModel values allows for a maximum of 255 standards- based Message Processing Models, and for a maximum of 256 Message Processing Models per enterprise. It is believed that the assignment of new messageProcessingModel values will be rare in practice because the larger the number of simultaneously utilized Message Processing Models, the larger the chance that interoperability will suffer. It is believed that such a range will be sufficient. In the unlikely event that the standards committee finds this number to be insufficient over time, an enterprise number can be allocated to obtain an additional 256 possible values. Note that the most significant bit must be zero; hence, there are 23 bits allocated for various organizations to design and define non-standard messageProcessingModels. This limits the ability to define new proprietary implementations of Message Processing Models to the first 8,388,608 enterprises. It is worthwhile to note that, in its encoded form, the messageProcessingModel value will normally require only a single byte since, in practice, the leftmost bits will be zero for most messages and sign extension is suppressed by the encoding rules. As of this writing, there are several values of messageProcessingModel defined for use with SNMP. They are as follows: 0 reserved for SNMPv1 1 reserved for SNMPv2c 2 reserved for SNMPv2u and SNMPv2* 3 reserved for SNMPv3 "
    status = "current"
    subtypeSpec = Integer32.subtypeSpec + ValueRangeConstraint(0, 2147483647)


class SnmpSecurityLevel(TextualConvention, Integer32):
    description = "A Level of Security at which SNMP messages can be sent or with which operations are being processed; in particular, one of: noAuthNoPriv - without authentication and without privacy, authNoPriv - with authentication but without privacy, authPriv - with authentication and with privacy. These three values are ordered such that noAuthNoPriv is less than authNoPriv and authNoPriv is less than authPriv. "
    status = "current"
    subtypeSpec = Integer32.subtypeSpec + ConstraintsUnion(
        SingleValueConstraint(1, 2, 3)
    )
    namedValues = NamedValues(("noAuthNoPriv", 1), ("authNoPriv", 2), ("authPriv", 3))


class SnmpAdminString(TextualConvention, OctetString):
    description = "An octet string containing administrative information, preferably in human-readable form. To facilitate internationalization, this information is represented using the ISO/IEC IS 10646-1 character set, encoded as an octet string using the UTF-8 transformation format described in [RFC2279]. Since additional code points are added by amendments to the 10646 standard from time to time, implementations must be prepared to encounter any code point from 0x00000000 to 0x7fffffff. Byte sequences that do not correspond to the valid UTF-8 encoding of a code point or are outside this range are prohibited. The use of control codes should be avoided. When it is necessary to represent a newline, the control code sequence CR LF should be used. The use of leading or trailing white space should be avoided. For code points not directly supported by user interface hardware or software, an alternative means of entry and display, such as hexadecimal, may be provided. For information encoded in 7-bit US-ASCII, the UTF-8 encoding is identical to the US-ASCII encoding. UTF-8 may require multiple bytes to represent a single character / code point; thus the length of this object in octets may be different from the number of characters encoded. Similarly, size constraints refer to the number of encoded octets, not the number of characters represented by an encoding. Note that when this TC is used for an object that is used or envisioned to be used as an index, then a SIZE restriction MUST be specified so that the number of sub-identifiers for any object instance does not exceed the limit of 128, as defined by [RFC3416]. Note that the size of an SnmpAdminString object is measured in octets, not characters. "
    status = "current"
    displayHint = "255t"
    encoding = "utf-8"
    subtypeSpec = OctetString.subtypeSpec + ValueSizeConstraint(0, 255)


snmpFrameworkAdmin = MibIdentifier((1, 3, 6, 1, 6, 3, 10, 1))
snmpFrameworkMIBObjects = MibIdentifier((1, 3, 6, 1, 6, 3, 10, 2))
snmpFrameworkMIBConformance = MibIdentifier((1, 3, 6, 1, 6, 3, 10, 3))
snmpEngine = MibIdentifier((1, 3, 6, 1, 6, 3, 10, 2, 1))
snmpEngineID = MibScalar((1, 3, 6, 1, 6, 3, 10, 2, 1, 1), SnmpEngineID()).setMaxAccess(
    "readonly"
)
if mibBuilder.loadTexts:
    snmpEngineID.setStatus("current")
if mibBuilder.loadTexts:
    snmpEngineID.setDescription(
        "An SNMP engine's administratively-unique identifier. This information SHOULD be stored in non-volatile storage so that it remains constant across re-initializations of the SNMP engine. "
    )
snmpEngineBoots = MibScalar(
    (1, 3, 6, 1, 6, 3, 10, 2, 1, 2),
    Integer32().subtype(subtypeSpec=ValueRangeConstraint(1, 2147483647)),
).setMaxAccess("readonly")
if mibBuilder.loadTexts:
    snmpEngineBoots.setStatus("current")
if mibBuilder.loadTexts:
    snmpEngineBoots.setDescription(
        "The number of times that the SNMP engine has (re-)initialized itself since snmpEngineID was last configured. "
    )
snmpEngineTime = (
    MibScalar(
        (1, 3, 6, 1, 6, 3, 10, 2, 1, 3),
        Integer32().subtype(subtypeSpec=ValueRangeConstraint(0, 2147483647)),
    )
    .setUnits("seconds")
    .setMaxAccess("readonly")
)
if mibBuilder.loadTexts:
    snmpEngineTime.setStatus("current")
if mibBuilder.loadTexts:
    snmpEngineTime.setDescription(
        "The number of seconds since the value of the snmpEngineBoots object last changed. When incrementing this object's value would cause it to exceed its maximum, snmpEngineBoots is incremented as if a re-initialization had occurred, and this object's value consequently reverts to zero. "
    )
snmpEngineMaxMessageSize = MibScalar(
    (1, 3, 6, 1, 6, 3, 10, 2, 1, 4),
    Integer32().subtype(subtypeSpec=ValueRangeConstraint(484, 2147483647)),
).setMaxAccess("readonly")
if mibBuilder.loadTexts:
    snmpEngineMaxMessageSize.setStatus("current")
if mibBuilder.loadTexts:
    snmpEngineMaxMessageSize.setDescription(
        "The maximum length in octets of an SNMP message which this SNMP engine can send or receive and process, determined as the minimum of the maximum message size values supported among all of the transports available to and supported by the engine. "
    )
snmpAuthProtocols = ObjectIdentity((1, 3, 6, 1, 6, 3, 10, 1, 1))
if mibBuilder.loadTexts:
    snmpAuthProtocols.setStatus("current")
if mibBuilder.loadTexts:
    snmpAuthProtocols.setDescription(
        "Registration point for standards-track authentication protocols used in SNMP Management Frameworks. "
    )
snmpPrivProtocols = ObjectIdentity((1, 3, 6, 1, 6, 3, 10, 1, 2))
if mibBuilder.loadTexts:
    snmpPrivProtocols.setStatus("current")
if mibBuilder.loadTexts:
    snmpPrivProtocols.setDescription(
        "Registration point for standards-track privacy protocols used in SNMP Management Frameworks. "
    )
snmpFrameworkMIBCompliances = MibIdentifier((1, 3, 6, 1, 6, 3, 10, 3, 1))
snmpFrameworkMIBGroups = MibIdentifier((1, 3, 6, 1, 6, 3, 10, 3, 2))
snmpFrameworkMIBCompliance = ModuleCompliance(
    (1, 3, 6, 1, 6, 3, 10, 3, 1, 1)
).setObjects(("SNMP-FRAMEWORK-MIB", "snmpEngineGroup"))

snmpFrameworkMIBCompliance = snmpFrameworkMIBCompliance.setStatus("current")
if mibBuilder.loadTexts:
    snmpFrameworkMIBCompliance.setDescription(
        "The compliance statement for SNMP engines which implement the SNMP Management Framework MIB. "
    )
snmpEngineGroup = ObjectGroup((1, 3, 6, 1, 6, 3, 10, 3, 2, 1)).setObjects(
    ("SNMP-FRAMEWORK-MIB", "snmpEngineID"),
    ("SNMP-FRAMEWORK-MIB", "snmpEngineBoots"),
    ("SNMP-FRAMEWORK-MIB", "snmpEngineTime"),
    ("SNMP-FRAMEWORK-MIB", "snmpEngineMaxMessageSize"),
)
snmpEngineGroup = snmpEngineGroup.setStatus("current")
if mibBuilder.loadTexts:
    snmpEngineGroup.setDescription(
        "A collection of objects for identifying and determining the configuration and current timeliness values of an SNMP engine. "
    )
mibBuilder.exportSymbols(
    "SNMP-FRAMEWORK-MIB",
    PYSNMP_MODULE_ID=snmpFrameworkMIB,
    SnmpAdminString=SnmpAdminString,
    SnmpEngineID=SnmpEngineID,
    SnmpMessageProcessingModel=SnmpMessageProcessingModel,
    SnmpSecurityLevel=SnmpSecurityLevel,
    SnmpSecurityModel=SnmpSecurityModel,
    snmpAuthProtocols=snmpAuthProtocols,
    snmpEngine=snmpEngine,
    snmpEngineBoots=snmpEngineBoots,
    snmpEngineGroup=snmpEngineGroup,
    snmpEngineID=snmpEngineID,
    snmpEngineMaxMessageSize=snmpEngineMaxMessageSize,
    snmpEngineTime=snmpEngineTime,
    snmpFrameworkAdmin=snmpFrameworkAdmin,
    snmpFrameworkMIB=snmpFrameworkMIB,
    snmpFrameworkMIBCompliance=snmpFrameworkMIBCompliance,
    snmpFrameworkMIBCompliances=snmpFrameworkMIBCompliances,
    snmpFrameworkMIBConformance=snmpFrameworkMIBConformance,
    snmpFrameworkMIBGroups=snmpFrameworkMIBGroups,
    snmpFrameworkMIBObjects=snmpFrameworkMIBObjects,
    snmpPrivProtocols=snmpPrivProtocols,
)
