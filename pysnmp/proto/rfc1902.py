#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The SMIv2 types: what an SNMPv2 value can be."""

import struct

from pyasn1.codec.ber import decoder, encoder
from pyasn1.error import PyAsn1Error
from pyasn1.type import constraint, namedtype, namedval, tag, univ

from pysnmp.proto import error

__all__ = [
    "OPAQUE_DOUBLE_TAG",
    "OPAQUE_FLOAT_TAG",
    "Bits",
    "Counter32",
    "Counter64",
    "Double",
    "Float",
    "Gauge32",
    "Integer",
    "Integer32",
    "IpAddress",
    "Null",
    "ObjectIdentifier",
    "OctetString",
    "Opaque",
    "TimeTicks",
    "Unsigned32",
    "decodeOpaqueReal",
]


class Null(univ.Null):
    """Creates an instance of SNMP Null class.

    :py:class:`~pysnmp.proto.rfc1902.Null` type represents the absence
    of value.

    Parameters
    ----------
    initializer: str
        Python string object. Must be an empty string.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Null('')
        <Null value object, payload []>
        >>>
    """


class Integer32(univ.Integer):
    """Creates an instance of SNMP Integer32 class.

    :py:class:`~pysnmp.proto.rfc1902.Integer32` type represents
    integer-valued information between -2147483648 to 2147483647
    inclusive (:RFC:`1902#section-7.1.1`). This type is indistinguishable
    from the :py:class:`~pysnmp.proto.rfc1902.Integer` type.
    The :py:class:`~pysnmp.proto.rfc1902.Integer32` type may be sub-typed
    to be more constrained than the base
    :py:class:`~pysnmp.proto.rfc1902.Integer32` type.

    Parameters
    ----------
    initializer : int
        Python integer in range between -2147483648 to 2147483647 inclusive
        or :py:class:`~pysnmp.proto.rfc1902.Integer32`.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Integer32(1234)
        <Integer32 value object, payload [1234]>
        >>> Integer32(1) > 2
        False
        >>> Integer32(1) + 1
        <Integer32 value object, payload [2]>
        >>> int(Integer32(321))
        321
        >>> SmallInteger = Integer32.withRange(1,3)
        >>> SmallInteger(1)
        <Integer32 value object, payload [1]>
        >>> DiscreetInteger = Integer32.withValues(4, 8, 1)
        >>> DiscreetInteger(4)
        <Integer32 value object, payload [4]>
        >>>

    """

    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        -2147483648, 2147483647
    )

    @classmethod
    def withValues(cls, *values):
        """Create a subclass with discreet values constraint."""

        class X(cls):
            subtypeSpec = cls.subtypeSpec + constraint.SingleValueConstraint(*values)

        X.__name__ = cls.__name__
        return X

    @classmethod
    def withRange(cls, minimum, maximum):
        """Create a subclass with value range constraint."""

        class X(cls):
            subtypeSpec = cls.subtypeSpec + constraint.ValueRangeConstraint(
                minimum, maximum
            )

        X.__name__ = cls.__name__
        return X


class Integer(Integer32):
    """Creates an instance of SNMP INTEGER class.

    The :py:class:`~pysnmp.proto.rfc1902.Integer` type represents
    integer-valued information as named-number enumerations
    (:RFC:`1902#section-7.1.1`). This type inherits and is indistinguishable
    from :py:class:`~pysnmp.proto.rfc1902.Integer32` class.
    The :py:class:`~pysnmp.proto.rfc1902.Integer` type may be sub-typed
    to be more constrained than the base
    :py:class:`~pysnmp.proto.rfc1902.Integer` type.

    Parameters
    ----------
    initializer : int
        Python integer in range between -2147483648 to 2147483647 inclusive
        or :py:class:`~pysnmp.proto.rfc1902.Integer`  class instance.
        In case of named-numbered enumerations, initialization is also
        possible by enumerated literal.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Integer(1234)
        <Integer value object, payload [1234]>
        >>> Integer(1) > 2
        False
        >>> Integer(1) + 1
        <Integer value object, payload [2]>
        >>> int(Integer(321))
        321
        >>> SomeState = Integer.withNamedValues(enable=1, disable=0)
        >>> SomeState(1)
        <Integer value object, payload [enable]>
        >>> int(SomeState('disable'))
        0
        >>>

    """

    @classmethod
    def withNamedValues(cls, **values):
        """Create a subclass with discreet named values constraint.

        Reduce fully duplicate enumerations along the way.
        """
        enums = set(cls.namedValues.items())
        enums.update(values.items())

        class X(cls):
            namedValues = namedval.NamedValues(*enums)
            subtypeSpec = cls.subtypeSpec + constraint.SingleValueConstraint(
                *values.values()
            )

        X.__name__ = cls.__name__
        return X


class OctetString(univ.OctetString):
    r"""Creates an instance of SNMP OCTET STRING class.

    The :py:class:`~pysnmp.proto.rfc1902.OctetString` type represents
    arbitrary binary or text data (:RFC:`1902#section-7.1.2`).
    It may be sub-typed to be constrained in size.

    Parameters
    ----------
    strValue : str
        Python string or :py:class:`~pysnmp.proto.rfc1902.OctetString`
        class instance.

    Other Parameters
    ----------------
    hexValue : str
        Python string representing octets in a hexadecimal notation
        (e.g. DEADBEEF).

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> OctetString('some apples')
        <OctetString value object, payload [some apples]>
        >>> OctetString('some apples') + ' and oranges'
        <OctetString value object, payload [some apples and oranges]>
        >>> OctetString('some apples').asOctets()
        b'some apples'
        >>> OctetString('some apples').prettyPrint()
        'some apples'
        >>> SomeString = OctetString.withSize(3, 12)
        >>> SomeString(hexValue='deadbeef').asOctets()
        b'\xde\xad\xbe\xef'
        >>> SomeString(hexValue='deadbeef').prettyPrint()
        '0xdeadbeef'
        >>>

    """

    subtypeSpec = univ.OctetString.subtypeSpec + constraint.ValueSizeConstraint(
        0, 65535
    )

    # rfc1902 uses a notion of "fixed length string" what might mean
    # having zero-range size constraint applied. The following is
    # supposed to be used for setting and querying this property.

    fixedLength: int | None = None

    def setFixedLength(self, value):
        """Pin this string to an exact length, and return it for chaining.

        A fixed length is not a constraint pyasn1 carries: it is what tells the table
        index code how many sub-identifiers to take for this column, which it cannot
        work out from the value alone.
        """
        self.fixedLength = value
        return self

    def isFixedLength(self):
        """Whether a fixed length has been pinned."""
        return self.fixedLength is not None

    def getFixedLength(self):
        """The pinned length, or `None`."""
        return self.fixedLength

    def clone(self, *args, **kwargs):
        """Clone, carrying the fixed length across.

        pyasn1's clone knows nothing about the fixed length, so a plain clone would
        silently drop it and break indexing on the copy.
        """
        return univ.OctetString.clone(self, *args, **kwargs).setFixedLength(
            self.getFixedLength()
        )

    def subtype(self, *args, **kwargs):
        """Subtype, carrying the fixed length across, for the same reason as `clone`."""
        return univ.OctetString.subtype(self, *args, **kwargs).setFixedLength(
            self.getFixedLength()
        )

    @classmethod
    def withSize(cls, minimum, maximum):
        """Create a subclass with value size constraint."""

        class X(cls):
            subtypeSpec = cls.subtypeSpec + constraint.ValueSizeConstraint(
                minimum, maximum
            )

        X.__name__ = cls.__name__
        return X


class ObjectIdentifier(univ.ObjectIdentifier):
    """Creates an instance of SNMP OBJECT IDENTIFIER class.

    The :py:class:`~pysnmp.proto.rfc1902.ObjectIdentifier` type represents
    administratively assigned names (:RFC:`1902#section-7.1.3`).
    Supports sequence protocol where elements are integer sub-identifiers.

    Parameters
    ----------
    initializer: tuple, str
        Python tuple of up to 128 integers in range between 0 to 4294967295
        inclusive or Python string containing OID in "dotted" form or
        :py:class:`~pysnmp.proto.rfc1902.ObjectIdentifier`.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> ObjectIdentifier((1, 3, 6))
        <ObjectIdentifier value object, payload [1.3.6]>
        >>> ObjectIdentifier('1.3.6')
        <ObjectIdentifier value object, payload [1.3.6]>
        >>> tuple(ObjectIdentifier('1.3.6'))
        (1, 3, 6)
        >>> str(ObjectIdentifier('1.3.6'))
        '1.3.6'
        >>>

    """


class IpAddress(OctetString):
    r"""Creates an instance of SNMP IpAddress class.

    The :py:class:`~pysnmp.proto.rfc1902.IpAddress` class represents
    a 32-bit internet address as an OCTET STRING of length 4, in network
    byte-order (:RFC:`1902#section-7.1.5`).

    Parameters
    ----------
    strValue : str
        The same as :py:class:`~pysnmp.proto.rfc1902.OctetString`,
        additionally IPv4 address in dotted notation ('127.0.0.1').

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> IpAddress('127.0.0.1')
        <IpAddress value object, payload [127.0.0.1]>
        >>> IpAddress(hexValue='7f000001').prettyPrint()
        '127.0.0.1'
        >>> IpAddress(hexValue='7f000001').asOctets()
        b'\x7f\x00\x00\x01'
        >>> IpAddress('\x7f\x00\x00\x01')
        <IpAddress value object, payload [127.0.0.1]>
        >>>

    """

    tagSet = OctetString.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x00)
    )
    subtypeSpec = OctetString.subtypeSpec + constraint.ValueSizeConstraint(4, 4)
    fixedLength = 4

    def prettyIn(self, value):
        """Accept an address as dotted quad, four octets, or another `IpAddress`."""
        if isinstance(value, str) and len(value) != 4:
            try:
                value = [int(x) for x in value.split(".")]
            except Exception as exc:
                raise error.ProtocolError(f"Bad IP address syntax {value}") from exc
        value = OctetString.prettyIn(self, value)
        if len(value) != 4:
            raise error.ProtocolError("Bad IP address syntax")
        return value

    def prettyOut(self, value):
        """Render as a dotted quad."""
        if value:
            return ".".join([str(x) for x in self.__class__(value).asNumbers()])
        else:
            return ""


class _WrappingInteger(univ.Integer):
    """An SMIv2 integer that wraps at its ceiling instead of overflowing.

    Counter32, Counter64 and TimeTicks all say the same thing in their
    definitions: the value increases until it reaches its maximum, "when it
    wraps around and starts increasing again from zero" (:RFC:`2578#section-7.1.6`,
    :RFC:`2578#section-7.1.10`, and modulo 2^32 for TimeTicks at
    :RFC:`2578#section-7.1.8`). Nothing implemented that wrap, so crossing the
    ceiling raised `ValueConstraintError` out of `clone()`'s constraint check --
    which, on `sysUpTime` and on the engine's own statistics counters, is a
    failure with nowhere useful to surface.

    Gauge32 and Unsigned32 deliberately do not inherit this: a Gauge latches at
    its maximum rather than wrapping (:RFC:`2578#section-7.1.7`).
    """

    #: 2 ** width. Subclasses set it; there is no sensible default.
    wrapModulus: int

    def __add__(self, value):
        """Add, wrapping at the ceiling rather than raising."""
        if not isinstance(value, (int, univ.Integer)):
            return NotImplemented

        return self.clone((self._value + int(value)) % self.wrapModulus)

    def __radd__(self, value):
        """Add, wrapping at the ceiling rather than raising."""
        return self.__add__(value)


class Counter32(_WrappingInteger):
    """Creates an instance of SNMP Counter32 class.

    :py:class:`~pysnmp.proto.rfc1902.Counter32` type represents
    a non-negative integer which monotonically increases until it
    reaches a maximum value of 4294967295, when it wraps around and
    starts increasing again from zero (:RFC:`1902#section-7.1.6`).

    Parameters
    ----------
    initializer : int
        Python integer in range between 0 to 4294967295 inclusive
        or any :py:class:`~pysnmp.proto.rfc1902.Integer`-based class.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Counter32(1234)
        <Counter32 value object, payload [1234]>
        >>> Counter32(1) + 1
        <Counter32 value object, payload [2]>
        >>> int(Counter32(321))
        321
        >>>

    """

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x01)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 4294967295
    )
    wrapModulus = 4294967296


class Gauge32(univ.Integer):
    """Creates an instance of SNMP Gauge32 class.

    :py:class:`~pysnmp.proto.rfc1902.Gauge32` type represents
    a non-negative integer, which may increase or decrease, but shall
    never exceed a maximum value. The maximum value can not be greater
    than 4294967295 (:RFC:`1902#section-7.1.7`).

    Parameters
    ----------
    initializer : int
        Python integer in range between 0 to 4294967295 inclusive
        or any :py:class:`~pysnmp.proto.rfc1902.Integer`-based class.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Gauge32(1234)
        <Gauge32 value object, payload [1234]>
        >>> Gauge32(1) + 1
        <Gauge32 value object, payload [2]>
        >>> int(Gauge32(321))
        321
        >>>

    """

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x02)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 4294967295
    )


class Unsigned32(univ.Integer):
    """Creates an instance of SNMP Unsigned32 class.

    :py:class:`~pysnmp.proto.rfc1902.Unsigned32` type represents
    integer-valued information between 0 and 4294967295
    (:RFC:`1902#section-7.1.11`).

    Parameters
    ----------
    initializer : int
        Python integer in range between 0 to 4294967295 inclusive
        or any :py:class:`~pysnmp.proto.rfc1902.Integer`-based class.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Unsigned32(1234)
        <Unsigned32 value object, payload [1234]>
        >>> Unsigned32(1) + 1
        <Unsigned32 value object, payload [2]>
        >>> int(Unsigned32(321))
        321
        >>>

    """

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x02)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 4294967295
    )


class TimeTicks(_WrappingInteger):
    """Creates an instance of SNMP TimeTicks class.

    :py:class:`~pysnmp.proto.rfc1902.TimeTicks` type represents
    a non-negative integer which represents the time, modulo 4294967296,
    in hundredths of a second between two epochs (:RFC:`1902#section-7.1.8`).

    Parameters
    ----------
    initializer : int
        Python integer in range between 0 to 4294967295 inclusive
        or any :py:class:`~pysnmp.proto.rfc1902.Integer`-based class.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> TimeTicks(1234)
        <TimeTicks value object, payload [1234]>
        >>> TimeTicks(1) + 1
        <TimeTicks value object, payload [2]>
        >>> int(TimeTicks(321))
        321
        >>>

    """

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x03)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 4294967295
    )
    wrapModulus = 4294967296


class Opaque(univ.OctetString):
    r"""Creates an instance of SNMP Opaque class.

    The :py:class:`~pysnmp.proto.rfc1902.Opaque` type supports the
    capability to pass arbitrary ASN.1 syntax.  A value is encoded
    using the ASN.1 BER into a string of octets.  This, in turn, is
    encoded as an OCTET STRING, in effect "double-wrapping" the original
    ASN.1 value (:RFC:`1902#section-7.1.9`).

    What the inner value is, only the sender knows. One convention is common
    enough to be worth naming: a real number, which SMIv2 has no syntax for,
    carried under a tag of its own -- see
    :py:class:`~pysnmp.proto.rfc1902.Float`,
    :py:class:`~pysnmp.proto.rfc1902.Double` and
    :py:func:`~pysnmp.proto.rfc1902.decodeOpaqueReal`. This class does not read
    it; nothing reads an Opaque as a number unless asked.

    Parameters
    ----------
    strValue : str
        Python string or :py:class:`~pysnmp.proto.rfc1902.OctetString`-based
        class instance.

    Other Parameters
    ----------------
    hexValue : str
        Python string representing octets in a hexadecimal notation
        (e.g. DEADBEEF).

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Opaque('some apples')
        <Opaque value object, payload [some apples]>
        >>> Opaque('some apples') + ' and oranges'
        <Opaque value object, payload [some apples and oranges]>
        >>> Opaque('some apples').asOctets()
        b'some apples'
        >>> Opaque('some apples').prettyPrint()
        'some apples'
        >>> Opaque(hexValue='deadbeef').asOctets()
        b'\xde\xad\xbe\xef'
        >>> Opaque(hexValue='deadbeef').prettyPrint()
        '0xdeadbeef'
        >>>

    """

    tagSet = univ.OctetString.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x04)
    )


#: BER's high-tag-number form for a context class, primitive value: the tag
#: numbers draft-perkins-opaque-01 uses are above 30, so that is how they have
#: to be written. net-snmp spells this byte ``ASN_OPAQUE_TAG1``.
_NESTED_TAG_PREFIX = 0x9F

#: The tag a nested single-precision float carries
#: (`draft-perkins-opaque-01 <https://datatracker.ietf.org/doc/html/draft-perkins-opaque-01>`_,
#: ``ASN_OPAQUE_FLOAT`` to net-snmp).
OPAQUE_FLOAT_TAG = 0x78

#: The tag a nested double-precision float carries (``ASN_OPAQUE_DOUBLE``).
OPAQUE_DOUBLE_TAG = 0x79


def _nestedSyntax(tagId):
    """The BER spec of the value an Opaque carries under `tagId`.

    The payload is read and written as octets: what is inside them is an IEEE
    754 number, which ASN.1 has no type for, so only the tag and the length
    are ASN.1's to check.
    """

    class _Nested(univ.OctetString):
        tagSet = univ.OctetString.tagSet.tagImplicitly(
            tag.Tag(tag.tagClassContext, tag.tagFormatSimple, tagId)
        )

    return _Nested()


class _OpaqueReal(Opaque):
    """A real number carried inside an Opaque, the way net-snmp sends one.

    SMIv2 has no floating point syntax, so an agent with a real number to
    report wraps it in an `Opaque`: the octets are a nested BER value whose own
    tag says which real type it is
    (`draft-perkins-opaque-01 <https://datatracker.ietf.org/doc/html/draft-perkins-opaque-01>`_).
    The draft never became a standard, but net-snmp implements it and emits it
    -- ``UCD-SNMP-MIB``'s ``laLoadFloat`` is the everyday case -- so anything
    polling an snmpd for load averages meets it.

    On the wire this is an `Opaque` and nothing else: the tag is Opaque's, the
    octets are the nested value, and a peer that has never heard of the
    convention sees exactly what it saw before. Which is also why decoding is
    never automatic. An `Opaque` is a general envelope and agents put all
    sorts of things in it, so a value arrives as `Opaque` and becomes a number
    only when something asks: either by naming the type, ``Float(varBind[1])``,
    or by letting :py:func:`~pysnmp.proto.rfc1902.decodeOpaqueReal` read the
    nested tag and decide. A MIB whose objects are always reals can name the
    type as their syntax in a behavior fragment
    (:py:mod:`pysnmp.smi.mibs.behavior`) and have every value cast on arrival.

    Comparison stays octet comparison, as for any `Opaque`; take ``float()``
    of a value first to compare it as a number.
    """

    #: The nested value's tag. Subclasses set it; there is no default.
    nestedTag: int

    #: Spec of the nested value, built from `nestedTag`.
    nestedSyntax: univ.OctetString

    #: `struct` format of the payload the nested value carries, which fixes
    #: its width as well as how it is read.
    packFormat: str

    #: Significant decimal digits enough to tell any two values of this width
    #: apart, which is where rendering stops widening the number it prints.
    decimalDigits: int

    def prettyIn(self, value):
        """Accept a Python number, or the nested BER octets carrying one.

        A number -- or a string spelling one, or another real of either width
        -- is encoded. Anything else is taken as the octets of a nested value
        already, and read back to check the tag is this type's and the payload
        the right width, then re-encoded so a value's octets do not depend on
        which length form the sender chose.
        """
        if isinstance(value, _OpaqueReal):
            return self._pack(value.asFloat())

        if isinstance(value, (int, float)):
            return self._pack(value)

        if isinstance(value, str):
            try:
                number = float(value)
            except ValueError as exc:
                raise error.ProtocolError(
                    f"Bad {self.__class__.__name__} value {value!r}"
                ) from exc

            return self._pack(number)

        return self._pack(self._unpack(Opaque.prettyIn(self, value)))

    def prettyOut(self, value):
        """Render the number, not the octets it travels in."""
        return self._prettyReal(self._unpack(value))

    def asFloat(self):
        """The number this value carries, as a Python float."""
        return self._unpack(self._value)

    def __float__(self):
        """The number this value carries, as a Python float."""
        return self.asFloat()

    def _pack(self, number):
        """`number` as a nested BER value, tagged and sized for this type."""
        try:
            payload = struct.pack(self.packFormat, number)
        except (OverflowError, struct.error) as exc:
            raise error.ProtocolError(
                f"{number!r} does not fit a {self.__class__.__name__}"
            ) from exc

        return encoder.encode(self.nestedSyntax.clone(payload))

    def _unpack(self, octets):
        """The number `octets` carry, which must be this type's nested value."""
        try:
            nested, rest = decoder.decode(bytes(octets), asn1Spec=self.nestedSyntax)
        except PyAsn1Error as exc:
            raise error.ProtocolError(
                f"Not a {self.__class__.__name__}: {exc}"
            ) from exc

        payload = nested.asOctets()
        expected = struct.calcsize(self.packFormat)

        if rest or len(payload) != expected:
            raise error.ProtocolError(
                f"Not a {self.__class__.__name__}: {expected} octets expected, "
                f"{len(payload) + len(rest)} carried"
            )

        return struct.unpack(self.packFormat, payload)[0]

    def _prettyReal(self, number):
        """The shortest decimal that reads back as `number` at this width.

        A single-precision value has no exact short decimal form -- the float
        nearest 0.08 is 0.07999999821186066 as a Python float, which is a
        double -- and printing all of that says more about IEEE 754 than about
        what the agent reported. So widen the rendering until it round-trips,
        and no further. A value near this width's ceiling has no rendering that
        round-trips at all, since every rounding of it is past the ceiling, and
        falls back to what Python makes of the number.
        """
        expected = struct.pack(self.packFormat, number)

        for digits in range(1, self.decimalDigits + 1):
            text = f"{number:.{digits}g}"

            try:
                if struct.pack(self.packFormat, float(text)) == expected:
                    return text
            except (OverflowError, struct.error):
                continue

        return repr(number)


class Float(_OpaqueReal):
    r"""Creates an instance of a single-precision float inside an SNMP Opaque.

    The :py:class:`~pysnmp.proto.rfc1902.Float` type is an
    :py:class:`~pysnmp.proto.rfc1902.Opaque` whose octets are a nested BER
    value tagged 0x78, carrying an IEEE 754 single-precision number
    (`draft-perkins-opaque-01 <https://datatracker.ietf.org/doc/html/draft-perkins-opaque-01>`_).
    This is what net-snmp reports ``UCD-SNMP-MIB`` load averages as.

    Nothing decodes an `Opaque` as one of these on its own -- see
    :py:func:`~pysnmp.proto.rfc1902.decodeOpaqueReal`.

    Parameters
    ----------
    initializer : float
        Python float or int, a string spelling one, or the octets of a nested
        value already -- bytes, an :py:class:`~pysnmp.proto.rfc1902.Opaque`,
        or another :py:class:`~pysnmp.proto.rfc1902.Float`.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On a value too large for single precision, or octets that are not
            a float-tagged nested value.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Float(1.5)
        <Float value object, payload [1.5]>
        >>> float(Float(1.5))
        1.5
        >>> Float(1.5).asOctets()
        b'\x9fx\x04?\xc0\x00\x00'
        >>> Float(Opaque(hexValue='9f78043fc00000')).prettyPrint()
        '1.5'
        >>> Float(0.08).prettyPrint()
        '0.08'
        >>>

    """

    nestedTag = OPAQUE_FLOAT_TAG
    nestedSyntax = _nestedSyntax(OPAQUE_FLOAT_TAG)
    packFormat = ">f"
    decimalDigits = 9


class Double(_OpaqueReal):
    r"""Creates an instance of a double-precision float inside an SNMP Opaque.

    The :py:class:`~pysnmp.proto.rfc1902.Double` type is an
    :py:class:`~pysnmp.proto.rfc1902.Opaque` whose octets are a nested BER
    value tagged 0x79, carrying an IEEE 754 double-precision number
    (`draft-perkins-opaque-01 <https://datatracker.ietf.org/doc/html/draft-perkins-opaque-01>`_).
    It is the same convention as :py:class:`~pysnmp.proto.rfc1902.Float` at
    twice the width, and the width a Python float already is.

    Nothing decodes an `Opaque` as one of these on its own -- see
    :py:func:`~pysnmp.proto.rfc1902.decodeOpaqueReal`.

    Parameters
    ----------
    initializer : float
        Python float or int, a string spelling one, or the octets of a nested
        value already -- bytes, an :py:class:`~pysnmp.proto.rfc1902.Opaque`,
        or another :py:class:`~pysnmp.proto.rfc1902.Double`.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On octets that are not a double-tagged nested value.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Double(1.5)
        <Double value object, payload [1.5]>
        >>> float(Double(0.1))
        0.1
        >>> Double(1.5).asOctets()
        b'\x9fy\x08?\xf8\x00\x00\x00\x00\x00\x00'
        >>> Double(Opaque(hexValue='9f79083ff8000000000000')).prettyPrint()
        '1.5'
        >>>

    """

    nestedTag = OPAQUE_DOUBLE_TAG
    nestedSyntax = _nestedSyntax(OPAQUE_DOUBLE_TAG)
    packFormat = ">d"
    decimalDigits = 17


#: The real types, by the nested tag that identifies each.
_OPAQUE_REAL_TYPES = {Float.nestedTag: Float, Double.nestedTag: Double}


def decodeOpaqueReal(value):
    """Read an `Opaque` as a real number where its own tag says it is one.

    Returns a :py:class:`~pysnmp.proto.rfc1902.Float` or a
    :py:class:`~pysnmp.proto.rfc1902.Double` where `value`'s octets are tagged
    as one, and `value` unchanged where they are not -- so this can be applied
    to every `Opaque` a walk turns up without assuming any of them is a
    number.

    Octets whose tag claims a real but whose payload will not decode as one
    raise `pysnmp.proto.error.ProtocolError`, rather than passing for the
    Opaque they came in as: the sender said what it was sending.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> decodeOpaqueReal(Opaque(hexValue='9f78043fc00000')).prettyPrint()
        '1.5'
        >>> decodeOpaqueReal(Opaque('some apples')).prettyPrint()
        'some apples'
        >>>

    """
    octets = value.asOctets() if isinstance(value, univ.OctetString) else bytes(value)

    if len(octets) > 2 and octets[0] == _NESTED_TAG_PREFIX:
        real = _OPAQUE_REAL_TYPES.get(octets[1])

        if real is not None:
            return real(octets)

    return value


class Counter64(_WrappingInteger):
    """Creates an instance of SNMP Counter64 class.

    :py:class:`~pysnmp.proto.rfc1902.Counter64` type represents
    a non-negative integer which monotonically increases until it reaches
    a maximum value of 18446744073709551615, when it wraps around and starts
    increasing again from zero (:RFC:`1902#section-7.1.10`).

    Parameters
    ----------
    initializer : int
        Python integer in range between 0 to 4294967295 inclusive
        or any :py:class:`~pysnmp.proto.rfc1902.Integer`-based class.

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> Counter64(1234)
        <Counter64 value object, payload [1234]>
        >>> Counter64(1) + 1
        <Counter64 value object, payload [2]>
        >>> int(Counter64(321))
        321
        >>>

    """

    tagSet = univ.Integer.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, 0x06)
    )
    subtypeSpec = univ.Integer.subtypeSpec + constraint.ValueRangeConstraint(
        0, 18446744073709551615
    )
    wrapModulus = 18446744073709551616


class Bits(OctetString):
    r"""Creates an instance of SNMP BITS class.

    The :py:class:`~pysnmp.proto.rfc1902.Bits` type represents
    an enumeration of named bits. This collection is assigned non-negative,
    contiguous values, starting at zero. Only those named-bits so enumerated
    may be present in a value (:RFC:`1902#section-7.1.4`).

    The bits are named and identified by their position in the octet string.
    Position zero is the high order (or left-most) bit in the first octet of
    the string. Position 7 is the low order (or right-most) bit of the first
    octet of the string. Position 8 is the high order bit in the second octet
    of the string, and so on
    (`BITS Pseudotype <https://tools.ietf.org/html/draft-perkins-bits-00>`_).

    Parameters
    ----------
    strValue : str, tuple
        Sequence of bit names or a Python string (as a raw data) or
        :py:class:`~pysnmp.proto.rfc1902.OctetString` class instance.

    Other Parameters
    ----------------
    hexValue : str
        Python string representing octets in a hexadecimal notation
        (e.g. DEADBEEF).

    Raises
    ------
        pyasn1.error.PyAsn1Error
            On constraint violation or bad initializer.

    Examples
    --------
        >>> from pysnmp.proto.rfc1902 import *
        >>> SomeBits = Bits.withNamedBits(apple=0, orange=1, peach=2)
        >>> SomeBits(('apple', 'orange')).prettyPrint()
        'apple, orange'
        >>> SomeBits(('apple', 'orange'))
        <Bits value object, payload [apple, orange]>
        >>> SomeBits('\x80')
        <Bits value object, payload [apple]>
        >>> SomeBits(hexValue='80')
        <Bits value object, payload [apple]>
        >>> SomeBits(hexValue='80').prettyPrint()
        'apple'
        >>>

    """

    namedValues = namedval.NamedValues()

    def __new__(cls, *args, **kwargs):
        """Build a subclass on the fly when named bits are given to the constructor."""
        if "namedValues" in kwargs:
            Bits = cls.withNamedBits(**dict(kwargs.pop("namedValues")))
            return Bits(*args, **kwargs)

        return OctetString.__new__(cls)

    def prettyIn(self, bits):
        """Accept either bit names or the raw octets they pack into.

        Bit 0 is the high bit of the first octet, not the low bit -- :RFC:`1902` numbers
        them the other way round from how they would fall out of a shift.
        """
        if not isinstance(bits, (tuple, list)):
            return OctetString.prettyIn(self, bits)  # raw bitstring
        octets = []
        for bit in bits:  # tuple of named bits
            v = self.namedValues[bit]
            if v is None:
                raise error.ProtocolError(f"Unknown named bit {bit}")
            d, m = divmod(v, 8)
            if d >= len(octets):
                octets.extend([0] * (d - len(octets) + 1))
            octets[d] |= 0x01 << (7 - m)
        return OctetString.prettyIn(self, octets)

    def prettyOut(self, value):
        """Render as the names of the bits that are set, in bit order."""
        names = []
        ints = self.__class__(value).asNumbers()
        for i, v in enumerate(ints):
            v = ints[i]
            j = 7
            while j >= 0:
                if v & (0x01 << j):
                    name = self.namedValues[i * 8 + 7 - j]
                    if name is None:
                        name = f"UnknownBit-{i * 8 + 7 - j}"
                    names.append(name)
                j -= 1
        return ", ".join([str(x) for x in names])

    @classmethod
    def withNamedBits(cls, **values):
        """Create a subclass with discreet named bits constraint.

        Reduce fully duplicate enumerations along the way.
        """
        enums = set(cls.namedValues.items())
        enums.update(values.items())

        class X(cls):
            namedValues = namedval.NamedValues(*enums)

        X.__name__ = cls.__name__
        return X


class ObjectName(univ.ObjectIdentifier):
    pass


class SimpleSyntax(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("integer-value", Integer()),
        namedtype.NamedType("string-value", OctetString()),
        namedtype.NamedType("objectID-value", univ.ObjectIdentifier()),
    )


class ApplicationSyntax(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("ipAddress-value", IpAddress()),
        namedtype.NamedType("counter-value", Counter32()),
        namedtype.NamedType("timeticks-value", TimeTicks()),
        namedtype.NamedType("arbitrary-value", Opaque()),
        namedtype.NamedType("big-counter-value", Counter64()),
        # This conflicts with Counter32
        # namedtype.NamedType('unsigned-integer-value', Unsigned32()),
        namedtype.NamedType("gauge32-value", Gauge32()),
    )  # BITS misplaced?


class ObjectSyntax(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("simple", SimpleSyntax()),
        namedtype.NamedType("application-wide", ApplicationSyntax()),
    )
