#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Benchmarks for the protocol helper API (``pysnmp.proto.api``).

These helpers assemble and take apart PDUs. They are called for every
request built by a manager and for every response built by an agent.
"""

from payloads import IF_TABLE_OIDS, SYSTEM_OIDS, make_request, make_response

from pysnmp.proto import api


def test_build_get_request_v2c(benchmark):
    pMod = api.protoModules[api.protoVersion2c]

    @benchmark
    def _():
        pdu = pMod.GetRequestPDU()
        pMod.apiPDU.setDefaults(pdu)
        pMod.apiPDU.setVarBinds(pdu, [(oid, pMod.null) for oid in SYSTEM_OIDS])


def test_build_get_bulk_request_v2c(benchmark):
    pMod = api.protoModules[api.protoVersion2c]

    @benchmark
    def _():
        pdu = pMod.GetBulkRequestPDU()
        pMod.apiBulkPDU.setDefaults(pdu)
        pMod.apiBulkPDU.setNonRepeaters(pdu, 0)
        pMod.apiBulkPDU.setMaxRepetitions(pdu, 25)
        pMod.apiBulkPDU.setVarBinds(pdu, [(oid, pMod.null) for oid in SYSTEM_OIDS])


def test_set_var_binds_60_values(benchmark):
    pMod = api.protoModules[api.protoVersion2c]
    varBinds = [(oid, pMod.Counter32(idx)) for idx, oid in enumerate(IF_TABLE_OIDS)]

    pdu = pMod.GetResponsePDU()
    pMod.apiPDU.setDefaults(pdu)

    @benchmark
    def _():
        pMod.apiPDU.setVarBinds(pdu, varBinds)


def test_get_var_binds_60_values(benchmark):
    pMod = api.protoModules[api.protoVersion2c]
    msg = make_response(api.protoVersion2c, IF_TABLE_OIDS)
    pdu = pMod.apiMessage.getPDU(msg)

    benchmark(pMod.apiPDU.getVarBinds, pdu)


def test_build_response_from_request_v2c(benchmark):
    """The agent side: derive a response PDU out of the request PDU."""
    pMod = api.protoModules[api.protoVersion2c]
    reqMsg = make_request(api.protoVersion2c, SYSTEM_OIDS)
    reqPDU = pMod.apiMessage.getPDU(reqMsg)

    @benchmark
    def _():
        rspPDU = pMod.apiPDU.getResponse(reqPDU)
        pMod.apiPDU.setVarBinds(
            rspPDU,
            [
                (oid, pMod.Integer(idx))
                for idx, (oid, _val) in enumerate(pMod.apiPDU.getVarBinds(reqPDU))
            ],
        )


def test_get_var_bind_table_v1(benchmark):
    pMod = api.protoModules[api.protoVersion1]
    reqMsg = make_request(api.protoVersion1, SYSTEM_OIDS)
    rspMsg = make_response(api.protoVersion1, SYSTEM_OIDS)
    reqPDU = pMod.apiMessage.getPDU(reqMsg)
    rspPDU = pMod.apiMessage.getPDU(rspMsg)

    benchmark(pMod.apiPDU.getVarBindTable, reqPDU, rspPDU)
