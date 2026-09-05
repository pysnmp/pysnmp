#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
from pyasn1.type import namedtype, namedval, univ

from pysnmp.proto import rfc1905

version = univ.Integer(namedValues=namedval.NamedValues(("version-2c", 1)))


class Message(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("version", version),
        namedtype.NamedType("community", univ.OctetString()),
        namedtype.NamedType("data", rfc1905.PDUs()),
    )
