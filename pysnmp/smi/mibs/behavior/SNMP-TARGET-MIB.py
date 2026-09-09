# RFC 3413 section 4.1.1: a tag value may not contain a delimiter -- space, tab,
# CR or LF -- and a tag list may not lead with one, end with one, or hold two in
# a row. The rule is stated in the DESCRIPTION clauses of SnmpTagValue and
# SnmpTagList and appears nowhere in their SYNTAX, which is an unconstrained
# 255-octet string, so it is checked here rather than by a subtype.

from pysnmp.smi import error as _error

_DELIMITERS = (" ", "\t", "\r", "\n")

_OctetString = OctetString


def _prettyInTagValue(self, value):
    for char in str(value):
        if char in _DELIMITERS:
            raise _error.SmiError(f"Delimiters not allowed in tag value {value!r}")

    return _OctetString.prettyIn(self, value)


def _prettyInTagList(self, value):
    inDelimiter = True

    for char in str(value):
        if char in _DELIMITERS:
            if inDelimiter:
                raise _error.SmiError(
                    f"Leading or multiple delimiters not allowed in tag list {value!r}"
                )
            inDelimiter = True
        else:
            inDelimiter = False

    if value and inDelimiter:
        raise _error.SmiError(f"Dangling delimiter not allowed in tag list {value!r}")

    return _OctetString.prettyIn(self, value)


SnmpTagValue.prettyIn = _prettyInTagValue
SnmpTagList.prettyIn = _prettyInTagList
