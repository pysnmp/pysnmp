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


#: RFC 4001 section 4.1 gives each concrete address family one fixed size, so a
#: bare InetAddress index -- one with no InetAddressType beside it to say what
#: it holds -- can still be read back as the family whose size it matches.
#: InetAddressDNS is deliberately absent: it is SIZE (1..255) and so matches
#: nothing in particular, and a DNS name happening to be 4 or 16 octets long is
#: the one case this cannot tell apart. The MIB's DESCRIPTION clause is the only
#: thing that could, and it is prose.
_lengthToTypeName = {
    4: "ipv4",
    8: "ipv4z",
    16: "ipv6",
    20: "ipv6z",
}


def _inferType(octets):
    """The concrete subtype an index of this length must be, or None.

    None means "no family claims this length" -- a DNS name, or something the
    RFC does not describe. The caller keeps the declared InetAddress in that
    case: it is variable-length and unconstrained, so it round-trips whatever
    the index actually held rather than guessing at it.
    """
    try:
        typeName = _lengthToTypeName[len(octets)]
    except KeyError:
        return None

    return InetAddress.typeMap[InetAddressType.namedValues[typeName]]


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


def _checkUnknown(parentIndex, octets):
    """Enforce what `unknown(0)` promises about the address beside it.

    `unknown` is the one InetAddressType named value with no entry in typeMap,
    because it names no concrete type. RFC 4001 section 4.1 is specific about
    what it does mean: it "MUST be used if the value of the corresponding
    InetAddress object is a zero-length string". So a zero-length address is
    exactly right and is carried as the declared InetAddress, while any other
    length is the sibling index and the value contradicting each other -- which
    is worth reporting rather than resolving by guessing at the length.
    """
    if octets:
        raise _error.SmiError(
            f"InetAddressType {parentIndex.prettyPrint()} requires a zero-length "
            f"InetAddress, got {len(octets)} octets"
        )


def _cloneFromName(cls, value, impliedFlag, parentRow, parentIndices):
    octets, rest = _splitIndex(value, impliedFlag)

    for parentIndex in reversed(parentIndices or ()):
        if isinstance(parentIndex, InetAddressType):
            try:
                concreteType = cls.typeMap[int(parentIndex)]
            except KeyError:
                _checkUnknown(parentIndex, octets)
                return cls(octets), rest

            # The octets, not a str of them. A TextualConvention given a str
            # parses it through the DISPLAY-HINT, so passing text would ask
            # InetAddressIPv4 to read four raw address bytes as "1d.1d.1d.1d"
            # -- which fails for every address not spelled in digits and dots.
            return concreteType.clone(octets), rest

    # No InetAddressType beside it. RFC 4001 recommends the pair but does not
    # require it, and shipped MIBs do not always follow the recommendation --
    # MPLS-VPN-MIB::mplsVpnVrfRouteEntry indexes on an InetAddress with no
    # address-type column anywhere in the INDEX clause. Raising here made every
    # table of that shape unusable, and because SmiError is a PyAsn1Error the
    # raise was swallowed by MibTableRow.getIndicesFromInstId(), which returned
    # the whole unconsumed remainder as one fabricated index instead.
    inferredType = _inferType(octets)

    return (cls(octets) if inferredType is None else inferredType.clone(octets)), rest


def _cloneAsName(self, impliedFlag, parentRow, parentIndices):
    for parentIndex in reversed(parentIndices or ()):
        if isinstance(parentIndex, InetAddressType):
            try:
                concreteType = self.typeMap[int(parentIndex)]
            except KeyError:
                _checkUnknown(parentIndex, self.asOctets())
                return _joinIndex(self, impliedFlag)

            # Bytes go in unparsed, as above.
            return _joinIndex(concreteType.clone(self.asOctets()), impliedFlag)

    # No InetAddressType beside it -- see _cloneFromName. The encoding is the
    # same either way, since the length prefix comes from the declared type and
    # the octets are the octets; resolving the family only decides how the value
    # renders once it is read back.
    return _joinIndex(self, impliedFlag)


InetAddress.cloneFromName = classmethod(_cloneFromName)
InetAddress.cloneAsName = _cloneAsName
