#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# PySNMP MIB module SNMPv2-CONF
#
# Hand-written, and not rendered from ASN.1 -- the header this carried until
# 2026 said "Produced by pysmi-0.1.3", which was never true of it.
#
# RFC 2580 defines SNMPv2-CONF entirely in macros: OBJECT-GROUP,
# NOTIFICATION-GROUP, MODULE-COMPLIANCE and AGENT-CAPABILITIES. A macro states
# how a MIB may be written, not an object with an OID, so a code generator
# reading the ASN.1 has nothing to emit for this module. What every other
# module means when it imports ModuleCompliance from here is the runtime class
# below, which is pysnmp's to define -- as with SNMPv2-SMI and SNMPv2-TC, and
# why pysmi lists all three among the modules it declines to compile.
#
(MibNode,) = mibBuilder.importSymbols("SNMPv2-SMI", "MibNode")


class ObjectGroup(MibNode):
    status = "current"
    objects = ()
    description = ""
    reference = ""

    def getStatus(self):
        return self.status

    def setStatus(self, v):
        self.status = v
        return self

    def getObjects(self):
        return getattr(self, "objects", ())

    def setObjects(self, *args, **kwargs):
        if kwargs.get("append"):
            self.objects += args
        else:
            self.objects = args
        return self

    def getDescription(self):
        return getattr(self, "description", "")

    def setDescription(self, v):
        self.description = v
        return self

    def getReference(self):
        return self.reference

    def setReference(self, v):
        self.reference = v
        return self

    def asn1Print(self):
        return """\
OBJECT-GROUP
  OBJECTS {{ {} }}
  DESCRIPTION "{}"
""".format(", ".join(list(self.getObjects())), self.getDescription())


class NotificationGroup(MibNode):
    status = "current"
    objects = ()
    description = ""
    reference = ""

    def getStatus(self):
        return self.status

    def setStatus(self, v):
        self.status = v
        return self

    def getObjects(self):
        return getattr(self, "objects", ())

    def setObjects(self, *args, **kwargs):
        if kwargs.get("append"):
            self.objects += args
        else:
            self.objects = args
        return self

    def getDescription(self):
        return getattr(self, "description", "")

    def setDescription(self, v):
        self.description = v
        return self

    def getReference(self):
        return self.reference

    def setReference(self, v):
        self.reference = v
        return self

    def asn1Print(self):
        return """\
NOTIFICATION-GROUP
  NOTIFICATIONS {{ {} }}
  DESCRIPTION "{}"
""".format(", ".join(list(self.getObjects())), self.getDescription())


class ModuleCompliance(MibNode):
    status = "current"
    objects = ()
    description = ""
    reference = ""

    def getStatus(self):
        return self.status

    def setStatus(self, v):
        self.status = v
        return self

    def getObjects(self):
        return getattr(self, "objects", ())

    def setObjects(self, *args, **kwargs):
        if kwargs.get("append"):
            self.objects += args
        else:
            self.objects = args
        return self

    def getDescription(self):
        return getattr(self, "description", "")

    def setDescription(self, v):
        self.description = v
        return self

    def getReference(self):
        return self.reference

    def setReference(self, v):
        self.reference = v
        return self

    def asn1Print(self):
        return """\
MODULE-COMPLIANCE
  OBJECT {{ {} }}
  DESCRIPTION "{}"
""".format(", ".join(list(self.getObjects())), self.getDescription())


class AgentCapabilities(MibNode):
    status = "current"
    description = ""
    reference = ""
    productRelease = ""

    def getStatus(self):
        return self.status

    def setStatus(self, v):
        self.status = v
        return self

    def getDescription(self):
        return getattr(self, "description", "")

    def setDescription(self, v):
        self.description = v
        return self

    def getReference(self):
        return self.reference

    def setReference(self, v):
        self.reference = v
        return self

    def getProductRelease(self):
        return self.productRelease

    def setProductRelease(self, v):
        self.productRelease = v
        return self

    # TODO: implement the rest of properties

    def asn1Print(self):
        return f"""\
AGENT-CAPABILITIES
  STATUS "{self.getStatus()}"
  PRODUCT-RELEASE "{self.getProductRelease()}"
  DESCRIPTION "{self.getDescription()}"
"""


mibBuilder.exportSymbols(
    "SNMPv2-CONF",
    ObjectGroup=ObjectGroup,
    NotificationGroup=NotificationGroup,
    ModuleCompliance=ModuleCompliance,
    AgentCapabilities=AgentCapabilities,
)
