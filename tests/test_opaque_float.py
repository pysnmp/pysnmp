"""Opaque-wrapped reals decode as numbers, and only when something asks.

SMIv2 has no floating point syntax, so an agent with a real number to report
carries it inside an ``Opaque``: the octets are a nested BER value tagged 0x78
for single precision or 0x79 for double, which is
`draft-perkins-opaque-01 <https://datatracker.ietf.org/doc/html/draft-perkins-opaque-01>`_.
net-snmp emits it for ``UCD-SNMP-MIB`` load averages, so polling an snmpd for
those met raw octets and a hand-rolled decoder at the caller. See #286.

The convention is a reading of an ``Opaque``, never a change to it: the wire
form is the same Opaque it always was, and nothing reads an Opaque as a number
without being asked, because agents put plenty of non-numbers in one.
"""

import struct

import pytest
from pyasn1.codec.ber import decoder, encoder

from pysnmp.proto import error, rfc1902, rfc1905
from pysnmp.proto.api import v2c
from pysnmp.proto.rfc1902 import Double, Float, Opaque, decodeOpaque

# What net-snmp puts on the wire inside the Opaque, for a value each: the
# two-octet high-tag-number form (0x9f, then the tag), a length, and the IEEE
# 754 payload.
FLOAT_OCTETS = bytes.fromhex("9f78043e19999a")  # 0.15, single precision
DOUBLE_OCTETS = bytes.fromhex("9f79083fc3333333333333")  # 0.15, double

LA_LOAD_FLOAT = "1.3.6.1.4.1.2021.10.1.6.1"  # UCD-SNMP-MIB::laLoadFloat.1


def test_a_float_encodes_the_way_netsnmp_does():
    assert Float(0.15).asOctets() == FLOAT_OCTETS


def test_a_double_encodes_the_way_netsnmp_does():
    assert Double(0.15).asOctets() == DOUBLE_OCTETS


def test_a_float_reads_back_the_number_it_was_given():
    assert (
        float(Float(FLOAT_OCTETS)) == struct.unpack(">f", bytes.fromhex("3e19999a"))[0]
    )


def test_a_double_reads_back_the_number_it_was_given():
    assert float(Double(DOUBLE_OCTETS)) == 0.15


def test_a_float_is_still_an_opaque_on_the_wire():
    # Tag 0x44, length 7, then the nested value -- indistinguishable from the
    # Opaque a peer that has never heard of the convention would send.
    assert encoder.encode(Float(0.15)) == bytes.fromhex("4407") + FLOAT_OCTETS


def test_a_float_travels_as_the_opaque_a_var_bind_declares():
    varBind = rfc1905.VarBind()
    v2c.apiVarBind.setOIDVal(varBind, (LA_LOAD_FLOAT, Float(0.15)))

    decoded, rest = decoder.decode(encoder.encode(varBind), asn1Spec=rfc1905.VarBind())
    _, value = v2c.apiVarBind.getOIDVal(decoded)

    assert not rest
    # What arrives is an Opaque. Reading it as a number is the caller's move.
    assert type(value) is Opaque
    assert float(decodeOpaque(value)) == float(Float(0.15))


@pytest.mark.parametrize(
    ("octets", "expected"),
    [
        pytest.param(FLOAT_OCTETS, Float, id="float"),
        pytest.param(DOUBLE_OCTETS, Double, id="double"),
    ],
)
def test_the_nested_tag_decides_which_real_it_is(octets, expected):
    assert type(decodeOpaque(Opaque(octets))) is expected


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("some apples", id="text"),
        pytest.param("", id="empty"),
        # Tagged as something else nested -- net-snmp's opaque Counter64.
        pytest.param(bytes.fromhex("9f34020100").decode("latin-1"), id="other-tag"),
    ],
)
def test_an_opaque_carrying_anything_else_comes_back_as_it_was(payload):
    opaque = Opaque(payload)

    assert decodeOpaque(opaque) is opaque


@pytest.mark.parametrize(
    "octets",
    [
        pytest.param(bytes.fromhex("9f78"), id="float-tag-alone"),
        pytest.param(bytes.fromhex("9f79"), id="double-tag-alone"),
    ],
)
def test_a_known_tag_with_nothing_after_it_is_reported(octets):
    # The tag declares the type with no length or payload behind it, which is
    # the same disagreement as a payload that will not decode, not an Opaque
    # that happens to carry two octets.
    with pytest.raises(error.ProtocolError):
        decodeOpaque(Opaque(octets))


def test_a_float_tagged_value_that_will_not_decode_is_reported():
    # The sender said it was sending a float, so this is a disagreement about
    # the protocol, not an Opaque that happens not to be one.
    with pytest.raises(error.ProtocolError):
        decodeOpaque(Opaque(bytes.fromhex("9f7802dead")))


@pytest.mark.parametrize(
    ("real", "octets"),
    [
        pytest.param(Float, DOUBLE_OCTETS, id="double-into-float"),
        pytest.param(Double, FLOAT_OCTETS, id="float-into-double"),
    ],
)
def test_each_real_refuses_the_other_one_s_tag(real, octets):
    with pytest.raises(error.ProtocolError):
        real(octets)


def test_a_float_refuses_octets_that_are_not_a_nested_value():
    with pytest.raises(error.ProtocolError):
        Float(Opaque("some apples"))


def test_a_float_refuses_a_number_too_large_for_single_precision():
    with pytest.raises(error.ProtocolError):
        Float(1e40)


def test_a_double_carries_what_single_precision_cannot():
    assert float(Double(1e40)) == 1e40


@pytest.mark.parametrize(
    ("real", "number", "rendered"),
    [
        pytest.param(Float, 0.15, "0.15", id="float-0.15"),
        pytest.param(Float, 0.08, "0.08", id="float-load-average"),
        pytest.param(Float, 1.5, "1.5", id="float-exact"),
        pytest.param(Float, 0, "0", id="float-zero"),
        pytest.param(Double, 0.1, "0.1", id="double-0.1"),
        pytest.param(Double, 1e40, "1e+40", id="double-large"),
    ],
)
def test_a_real_renders_as_the_number_not_the_octets(real, number, rendered):
    # Single precision has no exact short decimal form -- the float nearest
    # 0.08 is 0.07999999821186066 -- so rendering widens only until it reads
    # back as the same value.
    assert real(number).prettyPrint() == rendered


@pytest.mark.parametrize(
    ("real", "number"),
    [
        # The ceiling of each width, where a shorter rendering rounds past what
        # the width can hold, and the smallest value either can carry.
        pytest.param(
            Float, struct.unpack(">f", b"\x7f\x7f\xff\xff")[0], id="float-max"
        ),
        pytest.param(
            Float, -struct.unpack(">f", b"\x7f\x7f\xff\xff")[0], id="float-min"
        ),
        pytest.param(
            Float, struct.unpack(">f", b"\x00\x00\x00\x01")[0], id="float-denormal"
        ),
        pytest.param(Double, 1.7976931348623157e308, id="double-max"),
        pytest.param(Double, 5e-324, id="double-denormal"),
    ],
)
def test_a_value_at_the_edge_of_its_width_still_renders_as_itself(real, number):
    value = real(number)

    assert real(value.prettyPrint()).asOctets() == value.asOctets()


def test_the_rendered_number_reads_back_as_the_value_itself():
    value = Float(0.08)

    assert Float(value.prettyPrint()).asOctets() == value.asOctets()
    assert float(value) != 0.08  # single precision, told honestly


@pytest.mark.parametrize(
    ("real", "octets"),
    [
        pytest.param(Float, FLOAT_OCTETS, id="float"),
        pytest.param(Double, DOUBLE_OCTETS, id="double"),
    ],
)
def test_a_real_survives_the_clone_every_cast_goes_through(real, octets):
    # syntax.clone(value) is how a value is cast to the syntax its MIB
    # declares, and it feeds the current octets back through prettyIn.
    value = real(octets)

    assert value.clone().asOctets() == octets
    assert value.clone(0.5).asOctets() == real(0.5).asOctets()
    assert real(value).asOctets() == octets


def test_a_real_accepts_the_other_width_as_a_number():
    assert float(Double(Float(1.5))) == 1.5
    assert float(Float(Double(1.5))) == 1.5


def test_a_real_accepts_a_string_spelling_a_number():
    assert Float("1.5").asOctets() == Float(1.5).asOctets()


def test_a_string_that_is_not_a_number_is_reported():
    with pytest.raises(error.ProtocolError):
        Float("some apples")


def test_a_longer_length_form_normalizes_to_the_canonical_one():
    # BER lets a length be written long form; nobody emits it here, and a
    # value's octets should not depend on which form arrived.
    assert Float(bytes.fromhex("9f7881043e19999a")).asOctets() == FLOAT_OCTETS


def test_a_value_carrying_trailing_octets_is_reported():
    with pytest.raises(error.ProtocolError):
        Float(FLOAT_OCTETS + b"\x00")


def test_an_opaque_still_renders_as_octets():
    # Nothing about Opaque changed: the caller who was decoding the payload by
    # hand still sees what they saw.
    assert Opaque(FLOAT_OCTETS).prettyPrint() == "0x9f78043e19999a"


def test_hex_notation_reaches_the_same_value():
    assert Float(hexValue="9f78043e19999a").asOctets() == FLOAT_OCTETS


def test_the_types_are_reachable_from_the_high_level_api():
    from pysnmp import hlapi

    assert hlapi.Float is Float
    assert hlapi.Double is Double
    assert hlapi.decodeOpaque is decodeOpaque


def test_the_tags_are_the_ones_the_draft_names():
    assert (rfc1902.OPAQUE_FLOAT_TAG, rfc1902.OPAQUE_DOUBLE_TAG) == (0x78, 0x79)
