#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The SMIv1 types: what an SNMPv1 value can be."""

from pyasn1.error import PyAsn1Error
from pyasn1.type import constraint, namedtype, tag, univ

from pysnmp.proto import error
from pysnmp.smi.error import SmiError

__all__ = [
    "Counter",
    "Gauge",
    "IpAddress",
    "NetworkAddress",
    "ObjectName",
    "Opaque",
    "TimeTicks",
]


class IpAddress(univ.OctetString):
    """An IPv4 address, carried as four octets.

    Accepts and prints the familiar dotted-quad form, which is not what goes on
    the wire.
    """

    tagSet = univ.OctetString.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x00)
    )
    subtypeSpec = univ.OctetString.subtypeSpec + constraint.ValueSizeConstraint(4, 4)

    def prettyIn(self, value):
        if isinstance(value, str) and len(value) != 4:
            try:
                value = [int(x) for x in value.split(".")]
            except Exception as exc:
                raise error.ProtocolError(f"Bad IP address syntax {value}") from exc
        if len(value) != 4:
            raise error.ProtocolError("Bad IP address syntax")
        return univ.OctetString.prettyIn(self, value)

    def prettyOut(self, value):
        if value:
            return ".".join([str(x) for x in self.__class__(value).asNumbers()])
        else:
            return ""


class Counter(univ.Integer):
    """A 32-bit counter, which only ever increases and wraps at its maximum."""

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x01)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 4294967295
    )


class NetworkAddress(univ.Choice):
    """An address in any protocol family SNMPv1 knows, which is only IP."""

    componentType = namedtype.NamedTypes(namedtype.NamedType("internet", IpAddress()))

    def clone(self, value=univ.noValue, **kwargs):
        """Clone this instance.

        If *value* is specified, use its tag as the component type selector,
        and itself as the component value.

        :param value: (Optional) the component value.
        :type value: :py:obj:`pyasn1.type.base.Asn1Type`
        :return: the cloned instance.
        :rtype: :py:obj:`pysnmp.proto.rfc1155.NetworkAddress`
        :raise: :py:obj:`pysnmp.smi.error.SmiError`:
            if the type of *value* is not allowed for this Choice instance.
        """
        cloned = univ.Choice.clone(self, **kwargs)
        if value is not univ.noValue:
            if isinstance(value, NetworkAddress):
                value = value.getComponent()
            elif not isinstance(value, IpAddress):
                # IpAddress is the only supported type, perhaps forever because
                # this is SNMPv1.
                value = IpAddress(value)
            try:
                tagSet = value.tagSet
            except AttributeError as exc:
                raise PyAsn1Error(f"component value {value!r} has no tag set") from exc
            cloned.setComponentByType(tagSet, value)
        return cloned

    # RFC 1212, section 4.1.6:
    #
    #    "(5)  NetworkAddress-valued: `n+1' sub-identifiers, where `n'
    #          depends on the kind of address being encoded (the first
    #          sub-identifier indicates the kind of address, value 1
    #          indicates an IpAddress);"

    def cloneFromName(self, value, impliedFlag, parentRow, parentIndices):
        kind = value[0]
        clone = self.clone()
        if kind == 1:
            clone["internet"] = tuple(value[1:5])
            return clone, value[5:]
        else:
            raise SmiError(f"unknown NetworkAddress type {kind!r}")

    def cloneAsName(self, impliedFlag, parentRow, parentIndices):
        kind = self.getName()
        component = self.getComponent()
        if kind == "internet":
            return (1,) + tuple(component.asNumbers())
        else:
            raise SmiError(f"unknown NetworkAddress type {kind!r}")


class Gauge(univ.Integer):
    """A 32-bit gauge, which rises and falls and latches at its maximum."""

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x02)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 4294967295
    )


class TimeTicks(univ.Integer):
    """Hundredths of a second since some epoch the object's definition names."""

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x03)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 4294967295
    )


class Opaque(univ.OctetString):
    """Any other ASN.1 value, wrapped in octets so SNMPv1 can carry it."""

    tagSet = univ.OctetString.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x04)
    )


class ObjectName(univ.ObjectIdentifier):
    """The name of a managed object: an OID."""

    pass


class SimpleSyntax(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("number", univ.Integer()),
        namedtype.NamedType("string", univ.OctetString()),
        namedtype.NamedType("object", univ.ObjectIdentifier()),
        namedtype.NamedType("empty", univ.Null()),
    )


class ApplicationSyntax(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("address", NetworkAddress()),
        namedtype.NamedType("counter", Counter()),
        namedtype.NamedType("gauge", Gauge()),
        namedtype.NamedType("ticks", TimeTicks()),
        namedtype.NamedType("arbitrary", Opaque()),
    )


class ObjectSyntax(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("simple", SimpleSyntax()),
        namedtype.NamedType("application-wide", ApplicationSyntax()),
    )
