#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Reading the version field out of a message without decoding the rest.

Which version a message claims decides who parses it, so this has to run
before any of them do.
"""

from pyasn1.codec.ber import decoder, eoo
from pyasn1.error import PyAsn1Error
from pyasn1.type import univ

from pysnmp.proto.error import ProtocolError


def decodeMessageVersion(wholeMsg):
    """The version field of a message, read without decoding the rest.

    The dispatcher has to know which message processing model to hand a message to
    before it can be parsed, and the version is the second field of the outer
    sequence. So this decodes only as far as that integer and leaves the remainder
    alone, which also means a message for a model this engine does not have is
    never fully parsed.
    """
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
    except PyAsn1Error as exc:
        raise ProtocolError("Invalid BER at SNMP version component") from exc
    except (TypeError, ValueError) as exc:
        # Retained as defence in depth, not because a known input reaches it.
        # pyasn1 used to let plain Python exceptions escape this substrateFun
        # path (pyasn1 #140, #142, both fixed in 1.3.0rc2), and this is the
        # first thing an untrusted datagram touches, so nothing but
        # ProtocolError may escape here.
        raise ProtocolError(f"Malformed BER at SNMP version component: {exc}") from exc
    else:
        # Outside the try on purpose: ProtocolError derives from PyAsn1Error,
        # so raising it above would be caught by the handler two lines up and
        # come back out as "Invalid BER" instead.
        if eoo.endOfOctets.isSameTypeWith(ver):
            raise ProtocolError("EOO at SNMP version component")
        return ver
