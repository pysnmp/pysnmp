#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Building and reading PDUs without hard-coding a protocol version.

`protoModules[protoVersion2c]` gives the module for that version; the calls on
it are the same shape whichever version you asked for.
"""

from pysnmp.proto.api import v1, v2c, verdec

# Protocol versions
protoVersion1 = 0
protoVersion2c = 1
protoModules = {protoVersion1: v1, protoVersion2c: v2c}

decodeMessageVersion = verdec.decodeMessageVersion
