#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
from pyasn1.codec.ber import decoder, eoo
from pyasn1.error import PyAsn1Error
from pyasn1.type import univ

from pysnmp.proto.error import ProtocolError


def decodeMessageVersion(wholeMsg):
    try:
        seq, wholeMsg = decoder.decode(
            wholeMsg,
            asn1Spec=univ.Sequence(),
            recursiveFlag=False,
            substrateFun=lambda a, b, c: (a, b[:c]),
        )
        ver, wholeMsg = decoder.decode(
            wholeMsg,
            asn1Spec=univ.Integer(),
            recursiveFlag=False,
            substrateFun=lambda a, b, c: (a, b[:c]),
        )
        if eoo.endOfOctets.isSameTypeWith(ver):
            raise ProtocolError("EOO at SNMP version component")
        return ver
    except PyAsn1Error:
        raise ProtocolError("Invalid BER at SNMP version component")
    except (TypeError, ValueError) as exc:
        # Retained as defence in depth, not because a known input reaches it.
        # pyasn1 used to let plain Python exceptions escape this substrateFun
        # path (pyasn1 #140, #142, both fixed in 1.3.0rc2), and this is the
        # first thing an untrusted datagram touches, so nothing but
        # ProtocolError may escape here.
        raise ProtocolError(f"Malformed BER at SNMP version component: {exc}")
