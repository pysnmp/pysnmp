from pysnmp.smi.builder import MibBuilder


def test_transport_address_ipv6_pretty_in_accepts_bracketed_ipv6_text():
    mib_builder = MibBuilder()
    TextualConvention, = mib_builder.importSymbols('SNMPv2-TC', 'TextualConvention')
    TransportAddressIPv6, = mib_builder.importSymbols('TRANSPORT-ADDRESS-MIB', 'TransportAddressIPv6')

    expected = b'\x00' * 15 + b'\x01\x00\xa1'

    assert TextualConvention.prettyIn(TransportAddressIPv6(), '[::1]:161') == expected
    assert TransportAddressIPv6('[::1]:161').asOctets() == expected


def test_transport_address_ipv6_round_trips_display_hint_text():
    mib_builder = MibBuilder()
    TextualConvention, = mib_builder.importSymbols('SNMPv2-TC', 'TextualConvention')
    TransportAddressIPv6, = mib_builder.importSymbols('TRANSPORT-ADDRESS-MIB', 'TransportAddressIPv6')

    expected = b'\x00' * 15 + b'\x01\x00\xa1'
    rendered = TransportAddressIPv6(expected).prettyPrint()

    assert rendered == '[00:00:00:00:00:00:00:01]:161'
    assert TextualConvention.prettyIn(TransportAddressIPv6(), rendered) == expected


def test_transport_address_ipv6z_round_trips_display_hint_text():
    mib_builder = MibBuilder()
    TextualConvention, = mib_builder.importSymbols('SNMPv2-TC', 'TextualConvention')
    TransportAddressIPv6z, = mib_builder.importSymbols('TRANSPORT-ADDRESS-MIB', 'TransportAddressIPv6z')

    expected = b'\x00' * 15 + b'\x01' + b'\x00\x00\x00\x02' + b'\x00\xa1'
    rendered = TransportAddressIPv6z(expected).prettyPrint()

    assert rendered == '[00:00:00:00:00:00:00:01%2]:161'
    assert TextualConvention.prettyIn(TransportAddressIPv6z(), rendered) == expected
