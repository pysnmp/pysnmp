# RFC 4001 section 4: an InetAddress index is encoded as whatever concrete type
# the InetAddressType index preceding it in the same row names, so the same
# octets mean different things depending on a sibling index's value. SMIv2 has
# no syntax for that relation -- the RFC states it in the DESCRIPTION clauses of
# InetAddressType and InetAddress -- so it cannot be read off the module, and is
# written here instead.
#
# pysnmp dispatches on the presence of these members: MibTableRow.setFromName
# and MibTableRow.getAsName call cloneFromName/cloneAsName when the index object
# has them, and fall back to plain encoding when it does not.

from pysnmp.smi import error as _error

InetAddress.typeMap = {
    InetAddressType.namedValues["ipv4"]: InetAddressIPv4(),
    InetAddressType.namedValues["ipv6"]: InetAddressIPv6(),
    InetAddressType.namedValues["ipv4z"]: InetAddressIPv4z(),
    InetAddressType.namedValues["ipv6z"]: InetAddressIPv6z(),
    InetAddressType.namedValues["dns"]: InetAddressDNS(),
}


def _splitIndex(value, impliedFlag):
    """Take one InetAddress off the front of an instance OID, with its length.

    The encoding rule comes from the type the MIB *declares*, not from whatever
    InetAddressType names: InetAddress is OCTET STRING (SIZE (0..255)), so RFC
    2578 section 7.7 rule 3 puts a length sub-identifier in front of it, and
    resolving the concrete subtype does not take that away.

    That is why this cannot delegate to MibTableRow.setFromName() once the
    subtype is known. setFromName() reads the rule off the object it is handed,
    and InetAddressIPv4/IPv6/IPv4z/IPv6z are all fixed-length, so it would omit
    the prefix and read the address one sub-identifier short. Only
    InetAddressDNS -- variable-length, like the declared type -- came out right
    that way.
    """
    if impliedFlag:
        return tuple(value), ()

    length = value[0]
    octets = tuple(value[1 : length + 1])

    if len(octets) != length:
        raise _error.SmiError(
            f"Short InetAddress index: {length} octets declared, "
            f"{len(octets)} present in {value!r}"
        )

    return octets, value[length + 1 :]


def _joinIndex(value, impliedFlag):
    """Render one InetAddress into an instance OID, with its length.

    The inverse of `_splitIndex`, and fixed-length-blind for the same reason.
    """
    if impliedFlag:
        return value.asNumbers()

    return (len(value),) + value.asNumbers()


def _cloneFromName(cls, value, impliedFlag, parentRow, parentIndices):
    octets, rest = _splitIndex(value, impliedFlag)

    for parentIndex in reversed(parentIndices or ()):
        if isinstance(parentIndex, InetAddressType):
            try:
                concreteType = cls.typeMap[int(parentIndex)]
            except KeyError:
                continue

            # The octets, not a str of them. A TextualConvention given a str
            # parses it through the DISPLAY-HINT, so passing text would ask
            # InetAddressIPv4 to read four raw address bytes as "1d.1d.1d.1d"
            # -- which fails for every address not spelled in digits and dots.
            return concreteType.clone(octets), rest

    raise _error.SmiError(
        f"{cls.__name__} object encountered without preceding "
        f"InetAddressType-like index: {value!r}"
    )


def _cloneAsName(self, impliedFlag, parentRow, parentIndices):
    for parentIndex in reversed(parentIndices or ()):
        if isinstance(parentIndex, InetAddressType):
            try:
                concreteType = self.typeMap[int(parentIndex)]
            except KeyError:
                continue

            # Bytes go in unparsed, as above.
            return _joinIndex(concreteType.clone(self.asOctets()), impliedFlag)

    raise _error.SmiError(
        f"{self.__class__.__name__} object encountered without preceding "
        f"InetAddressType-like index: {self!r}"
    )


InetAddress.cloneFromName = classmethod(_cloneFromName)
InetAddress.cloneAsName = _cloneAsName
