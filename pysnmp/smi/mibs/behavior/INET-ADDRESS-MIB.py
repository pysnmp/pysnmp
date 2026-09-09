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


def _cloneFromName(cls, value, impliedFlag, parentRow, parentIndices):
    for parentIndex in reversed(parentIndices):
        if isinstance(parentIndex, InetAddressType):
            try:
                return parentRow.setFromName(
                    cls.typeMap[int(parentIndex)], value, impliedFlag, parentIndices
                )
            except KeyError:
                pass

    raise _error.SmiError(
        f"{cls.__name__} object encountered without preceding "
        f"InetAddressType-like index: {value!r}"
    )


def _cloneAsName(self, impliedFlag, parentRow, parentIndices):
    for parentIndex in reversed(parentIndices):
        if isinstance(parentIndex, InetAddressType):
            try:
                # The octets, not a str of them. A TextualConvention given a
                # str parses it through the DISPLAY-HINT, so decoding first
                # asks InetAddressIPv4 to read four raw address bytes as the
                # text "1d.1d.1d.1d" -- which fails for every address that is
                # not spelled in digits and dots. Bytes go in unparsed.
                return parentRow.getAsName(
                    self.typeMap[int(parentIndex)].clone(self.asOctets()),
                    impliedFlag,
                    parentIndices,
                )
            except KeyError:
                pass

    raise _error.SmiError(
        f"{self.__class__.__name__} object encountered without preceding "
        f"InetAddressType-like index: {self!r}"
    )


InetAddress.cloneFromName = classmethod(_cloneFromName)
InetAddress.cloneAsName = _cloneAsName
