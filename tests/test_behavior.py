"""Hand-written runtime behavior, and the two paths that apply it.

What is checked here is not that the fragments exist but that they are *in
effect* -- that a builder handing back ``SnmpTagValue`` hands back one that
rejects a delimiter, whichever way the module reached it. Both ways matter:
a module executed as generated Python, and a module synthesized from a corpus,
which never passes through a code generator at all and so was reached by no
splice upstream.

The behaviors themselves are the five relations the ASN.1 cannot state. Each
test names the RFC clause it is checking, because that clause is the only
specification the code has -- there is nothing in the module to compare against.
"""

import os
import shutil

import pytest

from pysnmp.smi import synthesis
from pysnmp.smi.builder import DirMibSource, MibBuilder
from pysnmp.smi.mibs import behavior

#: What a fragment is carried for. Named here rather than read from the package
#: so that deleting one is a test failure and not a silently smaller sweep.
FRAGMENTS = frozenset(
    {
        "INET-ADDRESS-MIB",
        "PYSNMP-USM-MIB",
        "SNMP-FRAMEWORK-MIB",
        "SNMP-TARGET-MIB",
        "SNMPv2-TM",
        "TRANSPORT-ADDRESS-MIB",
    }
)


@pytest.fixture(scope="module")
def builder():
    """A builder with every fragment-carrying module loaded."""
    built = MibBuilder()
    built.loadModules(*sorted(FRAGMENTS))

    return built


class TestPackage:
    """The fragment package itself."""

    def test_carries_exactly_the_expected_modules(self):
        assert behavior.modules() == FRAGMENTS

    def test_source_of_an_unknown_module_is_empty(self):
        assert behavior.source("NO-SUCH-MIB") == ""

    def test_apply_of_an_unknown_module_does_nothing(self):
        namespace = {}

        assert behavior.apply("NO-SUCH-MIB", namespace) is False
        assert namespace == {}

    def test_every_fragment_names_a_module_pysnmp_can_load(self, builder):
        # A fragment for a module nothing loads is dead code that still reads
        # as coverage.
        for module in behavior.modules():
            assert builder.getModulePath(module) is not None

    def test_no_fragment_is_carried_for_a_hand_written_module(self):
        # The point of the package is that the generated half stays
        # regenerable. A fragment beside a module pysnmp keeps a hand-edited
        # copy of would be the old arrangement wearing a new name -- so a
        # fragment may sit beside a module in pysnmp/smi/mibs only when that
        # module is one tools/regenerate_mibs.py renders from ASN.1.
        import pysnmp.smi.mibs as mibs
        from tools.regenerate_mibs import MODULES as RENDERED

        own = {
            entry[:-3]
            for entry in os.listdir(os.path.dirname(mibs.__file__))
            if entry.endswith(".py")
        }

        assert behavior.modules() & own <= set(RENDERED)


class TestInetAddress:
    """RFC 4001 section 4: the encoding of an InetAddress index."""

    def test_dispatch_members_are_attached(self, builder):
        (inetAddress,) = builder.importSymbols("INET-ADDRESS-MIB", "InetAddress")

        assert hasattr(inetAddress, "cloneFromName")
        assert hasattr(inetAddress, "cloneAsName")
        assert hasattr(inetAddress, "typeMap")

    def test_type_map_covers_every_address_type(self, builder):
        (inetAddress, inetAddressType) = builder.importSymbols(
            "INET-ADDRESS-MIB", "InetAddress", "InetAddressType"
        )

        for name in ("ipv4", "ipv6", "ipv4z", "ipv6z", "dns"):
            assert inetAddressType.namedValues[name] in inetAddress.typeMap

    def test_index_encoding_follows_the_preceding_type(self, builder):
        # The whole relation in one assertion: the same four octets encode as
        # an IPv4 address because the sibling index says ipv4.
        (inetAddress, inetAddressType) = builder.importSymbols(
            "INET-ADDRESS-MIB", "InetAddress", "InetAddressType"
        )
        (rowClass,) = builder.importSymbols("SNMPv2-SMI", "MibTableRow")

        row = rowClass((1, 3, 6, 1, 2, 1, 4, 34, 1))
        preceding = inetAddressType("ipv4")

        encoded = inetAddress(b"\x7f\x00\x00\x01").cloneAsName(False, row, (preceding,))

        assert encoded == (4, 127, 0, 0, 1)

    def test_raw_octets_are_not_parsed_as_display_hint_text(self, builder):
        # The bug the octets-not-str form fixes: an address whose bytes are not
        # spelled in digits and dots used to reach InetAddressIPv4 as text and
        # fail its DISPLAY-HINT. pysnmp/pysmi#231.
        (inetAddress, inetAddressType) = builder.importSymbols(
            "INET-ADDRESS-MIB", "InetAddress", "InetAddressType"
        )
        (rowClass,) = builder.importSymbols("SNMPv2-SMI", "MibTableRow")

        row = rowClass((1, 3, 6, 1, 2, 1, 4, 34, 1))

        encoded = inetAddress(b"\n\x00\x00\x01").cloneAsName(
            False, row, (inetAddressType("ipv4"),)
        )

        assert encoded == (4, 10, 0, 0, 1)

    # RFC 2578 section 7.7 rule 3: the declared type is OCTET STRING
    # (SIZE (0..255)), so the index carries a leading length whatever concrete
    # subtype InetAddressType resolves it to.

    @pytest.mark.parametrize(
        ("addressType", "octets", "expected"),
        [
            ("ipv4", b"\xc0\x00\x02\x01", (4, 192, 0, 2, 1)),
            ("ipv4z", b"\xc0\x00\x02\x01\x00\x00\x00\x07", (8, 192, 0, 2, 1, 0, 0, 0, 7)),
            (
                "ipv6",
                b" \x01\r\xb8" + b"\x00" * 11 + b"\x01",
                (16, 32, 1, 13, 184) + (0,) * 11 + (1,),
            ),
            ("dns", b"host.example", (12,) + tuple(b"host.example")),
        ],
    )
    def test_index_carries_its_length_prefix(
        self, builder, addressType, octets, expected
    ):
        (inetAddress, inetAddressType) = builder.importSymbols(
            "INET-ADDRESS-MIB", "InetAddress", "InetAddressType"
        )
        (rowClass,) = builder.importSymbols("SNMPv2-SMI", "MibTableRow")

        row = rowClass((1, 3, 6, 1, 2, 1, 4, 34, 1))
        preceding = inetAddressType(addressType)

        assert inetAddress(octets).cloneAsName(False, row, (preceding,)) == expected

    @pytest.mark.parametrize(
        ("addressType", "octets"),
        [
            ("ipv4", b"\xc0\x00\x02\x01"),
            ("ipv4z", b"\xc0\x00\x02\x01\x00\x00\x00\x07"),
            ("ipv6", b" \x01\r\xb8" + b"\x00" * 11 + b"\x01"),
            ("ipv6z", b" \x01\r\xb8" + b"\x00" * 11 + b"\x01\x00\x00\x00\x07"),
            ("dns", b"host.example"),
        ],
    )
    def test_index_round_trips(self, builder, addressType, octets):
        (inetAddress, inetAddressType) = builder.importSymbols(
            "INET-ADDRESS-MIB", "InetAddress", "InetAddressType"
        )
        (rowClass,) = builder.importSymbols("SNMPv2-SMI", "MibTableRow")

        row = rowClass((1, 3, 6, 1, 2, 1, 4, 34, 1))
        preceding = (inetAddressType(addressType),)

        encoded = inetAddress(octets).cloneAsName(False, row, preceding)
        # A trailing sub-identifier stands in for the rest of the row, so the
        # remainder is checked to be exactly what this index did not consume.
        decoded, rest = inetAddress.cloneFromName(
            encoded + (99,), False, row, preceding
        )

        assert decoded.asOctets() == octets
        assert rest == (99,)

    def test_implied_index_omits_the_length(self, builder):
        # RFC 2578 section 7.7: an IMPLIED index runs to the end of the OID, so
        # there is nothing to delimit and no length to carry.
        (inetAddress, inetAddressType) = builder.importSymbols(
            "INET-ADDRESS-MIB", "InetAddress", "InetAddressType"
        )
        (rowClass,) = builder.importSymbols("SNMPv2-SMI", "MibTableRow")

        row = rowClass((1, 3, 6, 1, 2, 1, 4, 34, 1))
        preceding = (inetAddressType("ipv4"),)

        encoded = inetAddress(b"\xc0\x00\x02\x01").cloneAsName(True, row, preceding)

        assert encoded == (192, 0, 2, 1)

        decoded, rest = inetAddress.cloneFromName(encoded, True, row, preceding)

        assert decoded.asOctets() == b"\xc0\x00\x02\x01"
        assert rest == ()

    def test_index_shorter_than_its_declared_length_raises(self, builder):
        from pysnmp.smi import error

        (inetAddress, inetAddressType) = builder.importSymbols(
            "INET-ADDRESS-MIB", "InetAddress", "InetAddressType"
        )
        (rowClass,) = builder.importSymbols("SNMPv2-SMI", "MibTableRow")

        row = rowClass((1, 3, 6, 1, 2, 1, 4, 34, 1))

        with pytest.raises(error.SmiError):
            inetAddress.cloneFromName(
                (4, 192, 0), False, row, (inetAddressType("ipv4"),)
            )

    def test_without_a_preceding_type_it_raises(self, builder):
        from pysnmp.smi import error

        (inetAddress,) = builder.importSymbols("INET-ADDRESS-MIB", "InetAddress")
        (rowClass,) = builder.importSymbols("SNMPv2-SMI", "MibTableRow")

        row = rowClass((1, 3, 6, 1, 2, 1, 4, 34, 1))

        with pytest.raises(error.SmiError):
            inetAddress(b"\x7f\x00\x00\x01").cloneAsName(False, row, ())


class TestSnmpTag:
    """RFC 3413 section 4.1.1: delimiters in tag values and tag lists."""

    @pytest.mark.parametrize("delimiter", [" ", "\t", "\r", "\n"])
    def test_every_delimiter_is_rejected_in_a_tag_value(self, builder, delimiter):
        # CR is the one pysnmp's 2017 copy missed: it listed tab twice and left
        # CR out, so "a\rb" was accepted for eight years.
        from pysnmp.smi import error

        (tagValue,) = builder.importSymbols("SNMP-TARGET-MIB", "SnmpTagValue")

        with pytest.raises(error.SmiError):
            tagValue(f"a{delimiter}b")

    def test_a_plain_tag_value_is_accepted(self, builder):
        (tagValue,) = builder.importSymbols("SNMP-TARGET-MIB", "SnmpTagValue")

        assert tagValue("router").asOctets() == b"router"

    @pytest.mark.parametrize("value", [" a", "a ", "a  b", "\ta"])
    def test_malformed_tag_lists_are_rejected(self, builder, value):
        from pysnmp.smi import error

        (tagList,) = builder.importSymbols("SNMP-TARGET-MIB", "SnmpTagList")

        with pytest.raises(error.SmiError):
            tagList(value)

    def test_a_well_formed_tag_list_is_accepted(self, builder):
        (tagList,) = builder.importSymbols("SNMP-TARGET-MIB", "SnmpTagList")

        assert tagList("a b c").asOctets() == b"a b c"

    def test_an_empty_tag_list_is_accepted(self, builder):
        (tagList,) = builder.importSymbols("SNMP-TARGET-MIB", "SnmpTagList")

        assert tagList("").asOctets() == b""


class TestSocketAddresses:
    """RFC 3417 section 3 and RFC 3419 section 3: values as socket addresses."""

    def test_udp_address_round_trips_a_socket_address(self, builder):
        (udpAddress,) = builder.importSymbols("SNMPv2-TM", "SnmpUDPAddress")

        assert tuple(udpAddress(("127.0.0.1", 161))) == ("127.0.0.1", 161)

    def test_udp_address_is_six_octets_network_order(self, builder):
        (udpAddress,) = builder.importSymbols("SNMPv2-TM", "SnmpUDPAddress")

        assert udpAddress(("1.2.3.4", 161)).asOctets() == b"\x01\x02\x03\x04\x00\xa1"

    def test_udp_address_indexes_like_a_socket_address(self, builder):
        (udpAddress,) = builder.importSymbols("SNMPv2-TM", "SnmpUDPAddress")

        value = udpAddress(("10.0.0.1", 1161))

        assert value[0] == "10.0.0.1"
        assert value[1] == 1161

    def test_transport_address_ipv4_round_trips(self, builder):
        (address,) = builder.importSymbols(
            "TRANSPORT-ADDRESS-MIB", "TransportAddressIPv4"
        )

        assert tuple(address(("192.0.2.1", 162))) == ("192.0.2.1", 162)

    def test_transport_address_ipv6_round_trips_with_flow_and_scope(self, builder):
        (address,) = builder.importSymbols(
            "TRANSPORT-ADDRESS-MIB", "TransportAddressIPv6"
        )

        assert tuple(address(("::1", 162))) == ("::1", 162, 0, 0)

    def test_transport_address_ipv6_is_eighteen_octets(self, builder):
        (address,) = builder.importSymbols(
            "TRANSPORT-ADDRESS-MIB", "TransportAddressIPv6"
        )

        assert len(address(("::1", 162)).asOctets()) == 18


class TestSnmpEngineID:
    """RFC 3411 section 5: the identifier an engine derives for itself."""

    def test_the_scalar_carries_a_value_not_a_schema(self, builder):
        # pysnmp/pysmi#236: a fragment runs after the module built its objects,
        # so setting defaultValue alone leaves snmpEngineID.syntax valueless and
        # every SnmpEngine() fails in config.addV1System.
        (engineId,) = builder.importSymbols("SNMP-FRAMEWORK-MIB", "snmpEngineID")

        assert engineId.syntax.isValue

    def test_the_default_starts_with_pysnmps_enterprise_number(self, builder):
        (engineIdType,) = builder.importSymbols("SNMP-FRAMEWORK-MIB", "SnmpEngineID")

        # 0x80000000 | 20408 -- the high bit RFC 3411 section 5 requires, then
        # the arc PYSNMP-MIB states.
        assert engineIdType.defaultValue[:4] == b"\x80\x00\x4f\xb8"

    def test_an_engine_starts_with_the_derived_identifier(self):
        from pysnmp.entity.engine import SnmpEngine

        assert SnmpEngine().snmpEngineID.asOctets()[:4] == b"\x80\x00\x4f\xb8"


class TestIdempotence:
    """Applying a fragment twice must leave the same behavior.

    pysmi splices its own copy of these fragments into the modules it bundles,
    so until that stops both run on every load, this package's last. That is
    only safe while a second application is a no-op.
    """

    @pytest.mark.parametrize("module", sorted(FRAGMENTS))
    def test_reapplying_changes_nothing_observable(self, builder, module):
        namespace = dict(builder.mibSymbols[module])
        namespace.update(
            {
                name: symbol
                for source in ("SNMPv2-SMI", "SNMPv2-TC", "ASN1")
                for name, symbol in builder.mibSymbols.get(source, {}).items()
            }
        )

        assert behavior.apply(module, namespace) is True

    def test_tag_value_still_rejects_after_a_second_application(self, builder):
        from pysnmp.smi import error

        (tagValue,) = builder.importSymbols("SNMP-TARGET-MIB", "SnmpTagValue")

        namespace = dict(builder.mibSymbols["SNMP-TARGET-MIB"])
        namespace["OctetString"] = builder.mibSymbols["ASN1"]["OctetString"]

        behavior.apply("SNMP-TARGET-MIB", namespace)

        with pytest.raises(error.SmiError):
            tagValue("a b")

        assert tagValue("router").asOctets() == b"router"

    def test_udp_address_still_round_trips_after_a_second_application(self, builder):
        (udpAddress,) = builder.importSymbols("SNMPv2-TM", "SnmpUDPAddress")

        namespace = dict(builder.mibSymbols["SNMPv2-TM"])
        namespace["TextualConvention"] = builder.mibSymbols["SNMPv2-TC"][
            "TextualConvention"
        ]

        behavior.apply("SNMPv2-TM", namespace)

        assert tuple(udpAddress(("127.0.0.1", 161))) == ("127.0.0.1", 161)


class TestFragmentNamespace:
    """The globals a fragment runs in when a module comes from a corpus."""

    class _Resolver:
        def __init__(self, builder, imports):
            self.builder = builder
            self.imports = imports

    def test_a_modules_own_symbols_are_present(self, builder):
        namespace = synthesis._FragmentNamespace(
            {"Local": object()}, self._Resolver(builder, {}), "X-MIB"
        )

        assert "Local" in namespace

    def test_an_imported_symbol_resolves_through_imports(self, builder):
        namespace = synthesis._FragmentNamespace(
            {}, self._Resolver(builder, {"DisplayString": "SNMPv2-TC"}), "X-MIB"
        )

        assert namespace["DisplayString"] is not None

    def test_the_textual_convention_class_resolves(self, builder):
        # The macro a MIB imports is TEXTUAL-CONVENTION; the class a fragment
        # names is TextualConvention, and IMPORTS will not answer for it.
        namespace = synthesis._FragmentNamespace(
            {}, self._Resolver(builder, {}), "X-MIB"
        )

        assert namespace["TextualConvention"].__name__ == "TextualConvention"

    def test_an_asn1_builtin_resolves(self, builder):
        namespace = synthesis._FragmentNamespace(
            {}, self._Resolver(builder, {}), "X-MIB"
        )

        assert namespace["OctetString"].__name__ == "OctetString"

    def test_a_resolved_name_is_cached_in_the_namespace(self, builder):
        namespace = synthesis._FragmentNamespace(
            {}, self._Resolver(builder, {}), "X-MIB"
        )

        first = namespace["OctetString"]

        assert namespace["OctetString"] is first

    def test_an_unknown_name_raises_key_error(self, builder):
        namespace = synthesis._FragmentNamespace(
            {}, self._Resolver(builder, {}), "X-MIB"
        )

        with pytest.raises(KeyError):
            namespace["NoSuchSymbol"]

    def test_builtins_still_resolve_for_a_fragment(self, builder):
        # A miss raises KeyError, which for a global lookup means builtins are
        # tried next. Fragments use isinstance, len and bytes.
        namespace = synthesis._FragmentNamespace(
            {}, self._Resolver(builder, {}), "X-MIB"
        )

        exec(compile("_x = isinstance(b'', bytes)", "<t>", "exec"), namespace)

        assert namespace["_x"] is True


pysmi_corpus = pytest.importorskip("pysmi.corpus.driver")

#: The modules the corpus under test carries, and so the ones the directory
#: source must not.
CORPUS_MODULES = ("SNMPv2-TM", "SNMP-TARGET-MIB")


@pytest.fixture(scope="module")
def synthesized(tmp_path_factory):
    """A builder that can only get these modules by synthesizing them.

    pysmi bundles generated copies of all three, so a builder with its default
    sources would never reach the corpus. The sources are cut back to a copy of
    pysnmp's own with the modules under test removed: pysnmp ships a rendering
    of the engine layer, and both of these are in it, so pointing at the real
    directory would resolve them from a file and measure nothing.
    """
    import pysmi
    from pysmi.corpus.driver import CorpusDriver, CorpusOutputs
    from pysmi.corpus.namespace import Namespace

    from pysnmp.smi.corpus import MibCorpus

    asn1 = os.path.join(os.path.dirname(pysmi.__file__), "mibs", "asn1")

    source = tmp_path_factory.mktemp("asn1")
    output = tmp_path_factory.mktemp("corpus")

    for module in CORPUS_MODULES:
        shutil.copy(os.path.join(asn1, module), str(source / module))

    outputs = CorpusOutputs(json=str(output / "json"), core_db=str(output / "core.db"))

    CorpusDriver(
        [Namespace(name="test", source=str(source), tier="standard")], outputs
    ).run()

    import pysnmp.smi.mibs as mibs

    core = os.path.dirname(mibs.__file__)
    without = str(tmp_path_factory.mktemp("core"))
    shutil.copytree(core, without, dirs_exist_ok=True)
    for module in CORPUS_MODULES:
        os.remove(os.path.join(without, f"{module}.py"))

    built = MibBuilder()
    built.setMibSources(
        DirMibSource(without), DirMibSource(os.path.join(without, "instances"))
    )
    built.setMibCorpus(MibCorpus(outputs.core_db))

    return built


class TestCorpusPath:
    """A module built from a corpus carries its behavior too.

    Nothing renders these modules -- objects are built straight from corpus
    rows -- so a splice at code generation time never reaches them. Before the
    fragments moved here, a corpus-synthesized SNMP-TARGET-MIB accepted a
    delimiter in a tag value and an SnmpUDPAddress was not a socket address.
    """

    def test_the_module_really_came_from_the_corpus(self, synthesized):
        synthesized.loadModules("SNMPv2-TM")

        assert synthesized.getModulePath("SNMPv2-TM").startswith("corpus:")

    def test_udp_address_round_trips(self, synthesized):
        synthesized.loadModules("SNMPv2-TM")

        (udpAddress,) = synthesized.importSymbols("SNMPv2-TM", "SnmpUDPAddress")

        assert tuple(udpAddress(("127.0.0.1", 161))) == ("127.0.0.1", 161)

    def test_tag_value_rejects_a_delimiter(self, synthesized):
        from pysnmp.smi import error

        synthesized.loadModules("SNMP-TARGET-MIB")

        (tagValue,) = synthesized.importSymbols("SNMP-TARGET-MIB", "SnmpTagValue")

        with pytest.raises(error.SmiError):
            tagValue("a b")

    def test_a_plain_tag_value_still_works(self, synthesized):
        synthesized.loadModules("SNMP-TARGET-MIB")

        (tagValue,) = synthesized.importSymbols("SNMP-TARGET-MIB", "SnmpTagValue")

        assert tagValue("router").asOctets() == b"router"
