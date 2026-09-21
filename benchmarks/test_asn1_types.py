#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Benchmarks for the SNMP base types defined in :RFC:`1902`.

Every value carried by an SNMP message goes through these classes, so their
construction, comparison and rendering cost shows up in every single
request the library handles.
"""

from pyasn1.type import namedval

from pysnmp.proto import rfc1902

SYS_DESCR = (
    "Linux edge-router-01 5.15.0-91-generic #101-Ubuntu SMP "
    "Tue Nov 14 13:30:08 UTC 2023 x86_64"
)

IF_TABLE_OIDS = [
    rfc1902.ObjectIdentifier((1, 3, 6, 1, 2, 1, 2, 2, 1, column, index))
    for index in range(1, 26)
    for column in (1, 2, 3, 8, 10, 16)
]


def test_integer32_from_int(benchmark):
    @benchmark
    def _():
        for value in range(256):
            rfc1902.Integer32(value)


def test_octet_string_from_text(benchmark):
    @benchmark
    def _():
        for _unused in range(128):
            rfc1902.OctetString(SYS_DESCR)


def test_octet_string_as_octets(benchmark):
    value = rfc1902.OctetString(SYS_DESCR)

    @benchmark
    def _():
        for _unused in range(256):
            value.asOctets()


def test_object_identifier_from_text(benchmark):
    @benchmark
    def _():
        for index in range(128):
            rfc1902.ObjectIdentifier("1.3.6.1.2.1.2.2.1.10.%d" % index)


def test_object_identifier_from_tuple(benchmark):
    @benchmark
    def _():
        for index in range(128):
            rfc1902.ObjectIdentifier((1, 3, 6, 1, 2, 1, 2, 2, 1, 10, index))


def test_object_identifier_pretty_print(benchmark):
    @benchmark
    def _():
        for oid in IF_TABLE_OIDS:
            oid.prettyPrint()


def test_object_identifier_is_prefix_of(benchmark):
    prefix = rfc1902.ObjectIdentifier((1, 3, 6, 1, 2, 1, 2, 2, 1, 10))

    @benchmark
    def _():
        for oid in IF_TABLE_OIDS:
            prefix.isPrefixOf(oid)


def test_object_identifier_sort(benchmark):
    oids = list(reversed(IF_TABLE_OIDS))

    @benchmark
    def _():
        sorted(oids)


def test_ip_address_from_text(benchmark):
    @benchmark
    def _():
        for index in range(128):
            rfc1902.IpAddress("10.0.%d.254" % (index % 256))


def test_time_ticks_pretty_print(benchmark):
    ticks = rfc1902.TimeTicks(4294967295)

    @benchmark
    def _():
        for _unused in range(128):
            ticks.prettyPrint()


def test_counter64_from_int(benchmark):
    @benchmark
    def _():
        for value in range(128):
            rfc1902.Counter64(value * 0x100000000)


def test_bits_from_names(benchmark):
    Notifications = rfc1902.Bits().clone(
        namedValues=namedval.NamedValues(
            ("coldStart", 0),
            ("warmStart", 1),
            ("linkDown", 2),
            ("linkUp", 3),
            ("authenticationFailure", 4),
        )
    )

    @benchmark
    def _():
        for _unused in range(64):
            Notifications.clone(("linkUp", "authenticationFailure"))


def test_integer_clone(benchmark):
    value = rfc1902.Integer(1)

    @benchmark
    def _():
        for index in range(256):
            value.clone(index)
