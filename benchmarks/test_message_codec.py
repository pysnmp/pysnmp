#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Benchmarks for BER serialisation of SNMP messages.

Encoding an outgoing message and decoding an incoming one is the single
hottest path of any SNMP manager or agent: it runs once (twice for
confirmed classes of PDU) per managed object polled.
"""

from payloads import IF_TABLE_OIDS, SYSTEM_OIDS, make_request, make_response
from pyasn1.codec.ber import decoder, encoder

from pysnmp.proto import api
from pysnmp.proto.api import decodeMessageVersion


def test_encode_get_request_v1(benchmark):
    msg = make_request(api.protoVersion1, SYSTEM_OIDS)

    benchmark(encoder.encode, msg)


def test_encode_get_request_v2c(benchmark):
    msg = make_request(api.protoVersion2c, SYSTEM_OIDS)

    benchmark(encoder.encode, msg)


def test_encode_response_v2c_60_varbinds(benchmark):
    msg = make_response(api.protoVersion2c, IF_TABLE_OIDS)

    benchmark(encoder.encode, msg)


def test_decode_get_request_v1(benchmark, v1_request_substrate):
    spec = api.protoModules[api.protoVersion1].Message()

    benchmark(decoder.decode, v1_request_substrate, asn1Spec=spec)


def test_decode_get_request_v2c(benchmark, v2c_request_substrate):
    spec = api.protoModules[api.protoVersion2c].Message()

    benchmark(decoder.decode, v2c_request_substrate, asn1Spec=spec)


def test_decode_response_v2c_60_varbinds(benchmark, v2c_response_substrate):
    spec = api.protoModules[api.protoVersion2c].Message()

    benchmark(decoder.decode, v2c_response_substrate, asn1Spec=spec)


def test_decode_message_version(benchmark, v2c_response_substrate):
    """Version sniffing runs on every datagram before full decoding."""

    @benchmark
    def _():
        for _unused in range(32):
            decodeMessageVersion(v2c_response_substrate)


def test_roundtrip_response_v2c(benchmark):
    """Encode then decode, the way a request/response exchange does it."""
    pMod = api.protoModules[api.protoVersion2c]
    msg = make_response(api.protoVersion2c, SYSTEM_OIDS)

    @benchmark
    def _():
        substrate = encoder.encode(msg)
        rspMsg, _rest = decoder.decode(substrate, asn1Spec=pMod.Message())
        pMod.apiPDU.getVarBinds(pMod.apiMessage.getPDU(rspMsg))


def test_encode_v1_trap(benchmark):
    pMod = api.protoModules[api.protoVersion1]

    trapPDU = pMod.TrapPDU()
    pMod.apiTrapPDU.setDefaults(trapPDU)
    pMod.apiTrapPDU.setGenericTrap(trapPDU, "linkDown")
    pMod.apiTrapPDU.setVarBinds(
        trapPDU, [((1, 3, 6, 1, 2, 1, 2, 2, 1, 1, 3), pMod.Integer(3))]
    )

    msg = pMod.Message()
    pMod.apiMessage.setDefaults(msg)
    pMod.apiMessage.setCommunity(msg, "public")
    pMod.apiMessage.setPDU(msg, trapPDU)

    benchmark(encoder.encode, msg)
