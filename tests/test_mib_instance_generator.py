"""Unit tests for the MIB instance generator tool."""

import importlib.util
import os

# Import the tool module directly
_tool_path = os.path.join(os.path.dirname(__file__), "..", "tools", "mib_instance_generator.py")
_spec = importlib.util.spec_from_file_location("mib_instance_generator", _tool_path)
mib_instance_generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mib_instance_generator)


class TestWalkMibSymbols:
    """Test the MIB symbol walker."""

    def test_walk_snmpv2_mib_scalars(self):
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        symbols = mib_instance_generator.walk_mib_symbols(mibBuilder, "SNMPv2-MIB")

        # SNMPv2-MIB should have scalar objects like sysDescr, sysObjectID
        assert "scalars" in symbols
        assert "sysDescr" in symbols["scalars"]
        assert "sysObjectID" in symbols["scalars"]

    def test_walk_snmpv2_mib_tables(self):
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        symbols = mib_instance_generator.walk_mib_symbols(mibBuilder, "SNMPv2-MIB")

        # sysORTable should be present
        assert "tables" in symbols
        assert "sysORTable" in symbols["tables"]
        assert "table_rows" in symbols
        assert "sysOREntry" in symbols["table_rows"]
        assert "sysORID" in symbols["table_columns"]
        assert "sysORID" not in symbols["scalars"]

    def test_walk_nonexistent_module(self):
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        symbols = mib_instance_generator.walk_mib_symbols(mibBuilder, "NONEXISTENT-MIB")
        assert symbols["scalars"] == {}
        assert symbols["table_columns"] == {}


class TestGenerateInstances:
    """Test the MIB instances file generator."""

    def test_generate_contains_module_name(self):
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        source = mib_instance_generator.generate_instances(
            mibBuilder, "SNMPv2-MIB", instance_mod_suffix="_test"
        )
        assert "SNMPv2-MIB_test" in source

    def test_generate_contains_scalar_instances(self):
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        source = mib_instance_generator.generate_instances(mibBuilder, "SNMPv2-MIB")
        assert "MibScalarInstance" in source
        assert "sysDescr" in source
        assert "sysObjectID" in source

    def test_generate_contains_export_symbols(self):
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        source = mib_instance_generator.generate_instances(mibBuilder, "SNMPv2-MIB")
        assert "mibBuilder.exportSymbols" in source

    def test_generate_valid_python(self):
        """The generated source should be syntactically valid Python."""
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        source = mib_instance_generator.generate_instances(mibBuilder, "SNMPv2-MIB")
        compile(source, "<test>", "exec")

    def test_generated_module_loads_scalar_and_table_instances(self):
        from pysnmp.smi.builder import MibBuilder

        mib_builder = MibBuilder()
        mib_builder.loadModules("SNMPv2-MIB")
        source = mib_instance_generator.generate_instances(mib_builder, "SNMPv2-MIB")
        exec(compile(source, "<generated>", "exec"), {"mibBuilder": mib_builder})

        scalar, column = mib_builder.importSymbols(
            "SNMPv2-MIB_instances", "sysDescr_inst", "sysORID_inst"
        )
        assert scalar.name == (1, 3, 6, 1, 2, 1, 1, 1, 0)
        assert column.name == (1, 3, 6, 1, 2, 1, 1, 9, 1, 2, 1)

    def test_generate_table_column_instances(self):
        from pysnmp.smi.builder import MibBuilder

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        source = mib_instance_generator.generate_instances(mibBuilder, "SNMPv2-MIB")
        # sysORID, sysORDescr, sysORUpTime are table columns
        assert "sysORID" in source
        assert "sysORDescr" in source


class TestDefaultValueForSyntax:
    """Test the default value selection for syntax types."""

    def test_integer_default(self):
        from pysnmp.proto.rfc1902 import Integer32

        val = mib_instance_generator._default_value_for_syntax(Integer32())
        assert val == "0"

    def test_octet_string_default(self):
        from pysnmp.proto.rfc1902 import OctetString

        val = mib_instance_generator._default_value_for_syntax(OctetString())
        assert val == '""'

    def test_object_identifier_default(self):
        from pysnmp.proto.rfc1902 import ObjectIdentifier

        val = mib_instance_generator._default_value_for_syntax(ObjectIdentifier())
        assert val == "(0,)"


def test_compile_local_asn1_and_generate_instances(tmp_path):
    (tmp_path / "SNMPv2-SMI.txt").write_text(
        """\
SNMPv2-SMI DEFINITIONS ::= BEGIN
iso OBJECT IDENTIFIER ::= { 1 }
org OBJECT IDENTIFIER ::= { iso 3 }
dod OBJECT IDENTIFIER ::= { org 6 }
internet OBJECT IDENTIFIER ::= { dod 1 }
private OBJECT IDENTIFIER ::= { internet 4 }
enterprises OBJECT IDENTIFIER ::= { private 1 }
END
""",
        encoding="utf-8",
    )
    (tmp_path / "SNMPv2-TC.txt").write_text(
        """\
SNMPv2-TC DEFINITIONS ::= BEGIN
DisplayString ::= OCTET STRING
END
""",
        encoding="utf-8",
    )
    (tmp_path / "SNMPv2-CONF.txt").write_text(
        """\
SNMPv2-CONF DEFINITIONS ::= BEGIN
END
""",
        encoding="utf-8",
    )
    mib_source = tmp_path / "not-the-module-name.txt"
    mib_source.write_text(
        """\
TEST-INSTANCE-MIB DEFINITIONS ::= BEGIN

IMPORTS
    MODULE-IDENTITY, OBJECT-TYPE, Integer32, enterprises
        FROM SNMPv2-SMI;

testInstanceMIB MODULE-IDENTITY
    LAST-UPDATED "202608280000Z"
    ORGANIZATION "PySNMP tests"
    CONTACT-INFO "none"
    DESCRIPTION "A test MIB."
    REVISION "202608280000Z"
    DESCRIPTION "Initial revision."
    ::= { enterprises 99999 }

testScalar OBJECT-TYPE
    SYNTAX Integer32 (0..100)
    MAX-ACCESS read-only
    STATUS current
    DESCRIPTION "A test scalar."
    ::= { testInstanceMIB 1 }

END
""",
        encoding="utf-8",
    )
    compiled = tmp_path / "compiled"
    compiled.mkdir()

    mib_builder, module_name = mib_instance_generator.compile_mib(str(mib_source), str(compiled))
    assert module_name == "TEST-INSTANCE-MIB"
    assert (compiled / "TEST-INSTANCE-MIB.py").is_file()
    assert "testScalar" in mib_builder.mibSymbols[module_name]

    source = mib_instance_generator.generate_instances(mib_builder, module_name)
    exec(compile(source, "<generated>", "exec"), {"mibBuilder": mib_builder})
    (instance,) = mib_builder.importSymbols("TEST-INSTANCE-MIB_instances", "testScalar_inst")
    assert instance.name == (1, 3, 6, 1, 4, 1, 99999, 1, 0)
    assert int(instance.syntax) == 0
