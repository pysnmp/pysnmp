#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

from typing import Any

from pysnmp.proto import rfc1157, rfc1905

readClassPDUs: dict[Any, int] = {
    rfc1157.GetRequestPDU.tagSet: 1,
    rfc1157.GetNextRequestPDU.tagSet: 1,
    rfc1905.GetRequestPDU.tagSet: 1,
    rfc1905.GetNextRequestPDU.tagSet: 1,
    rfc1905.GetBulkRequestPDU.tagSet: 1,
}

writeClassPDUs: dict[Any, int] = {rfc1157.SetRequestPDU.tagSet: 1, rfc1905.SetRequestPDU.tagSet: 1}

responseClassPDUs: dict[Any, int] = {
    rfc1157.GetResponsePDU.tagSet: 1,
    rfc1905.ResponsePDU.tagSet: 1,
    rfc1905.ReportPDU.tagSet: 1,
}

notificationClassPDUs: dict[Any, int] = {
    rfc1157.TrapPDU.tagSet: 1,
    rfc1905.SNMPv2TrapPDU.tagSet: 1,
    rfc1905.InformRequestPDU.tagSet: 1,
}

internalClassPDUs: dict[Any, int] = {rfc1905.ReportPDU.tagSet: 1}

confirmedClassPDUs: dict[Any, int] = {
    rfc1157.GetRequestPDU.tagSet: 1,
    rfc1157.GetNextRequestPDU.tagSet: 1,
    rfc1157.SetRequestPDU.tagSet: 1,
    rfc1905.GetRequestPDU.tagSet: 1,
    rfc1905.GetNextRequestPDU.tagSet: 1,
    rfc1905.GetBulkRequestPDU.tagSet: 1,
    rfc1905.SetRequestPDU.tagSet: 1,
    rfc1905.InformRequestPDU.tagSet: 1,
}

unconfirmedClassPDUs: dict[Any, int] = {
    rfc1157.GetResponsePDU.tagSet: 1,
    rfc1905.ResponsePDU.tagSet: 1,
    rfc1157.TrapPDU.tagSet: 1,
    rfc1905.ReportPDU.tagSet: 1,
    rfc1905.SNMPv2TrapPDU.tagSet: 1,
}
