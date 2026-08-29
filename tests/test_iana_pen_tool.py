"""Unit tests for the IANA PEN to MIB tool."""

import importlib.util
import os

# Import the tool module directly
_tool_path = os.path.join(os.path.dirname(__file__), "..", "tools", "iana_pen_to_mib.py")
_spec = importlib.util.spec_from_file_location("iana_pen_to_mib", _tool_path)
iana_pen_to_mib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iana_pen_to_mib)


SAMPLE_PEN_DATA = """\
Enterprise Number  Organization

1
ISO

2
IANA

3
IETF

11
UCLA

12
- Blank org -

13
Test Org Inc

20408
PySNMP Project
"""


class TestParseIanaPen:
    """Test the IANA PEN registry parser."""

    def test_parse_basic_entries(self):
        entries = iana_pen_to_mib.parse_iana_pen(SAMPLE_PEN_DATA)
        # Should find entries for ISO, IANA, IETF, UCLA, etc.
        numbers = [e[0] for e in entries]
        assert 1 in numbers  # ISO
        assert 2 in numbers  # IANA
        assert 3 in numbers  # IETF
        assert 11 in numbers  # UCLA
        assert 20408 in numbers  # PySNMP

    def test_parse_organization_name(self):
        entries = iana_pen_to_mib.parse_iana_pen(SAMPLE_PEN_DATA)
        iso_entry = [e for e in entries if e[0] == 1][0]
        assert iso_entry[1] == "ISO"

        pysnmp_entry = [e for e in entries if e[0] == 20408][0]
        assert "PySNMP" in pysnmp_entry[1]

    def test_parse_empty_data(self):
        entries = iana_pen_to_mib.parse_iana_pen("")
        assert entries == []

    def test_parse_no_header(self):
        entries = iana_pen_to_mib.parse_iana_pen("42\nAnswer Inc\n")
        assert len(entries) == 1
        assert entries[0][0] == 42
        assert "Answer" in entries[0][1]


class TestGenerateMibModule:
    """Test the MIB module generator."""

    def test_generate_contains_module_name(self):
        entries = [(1, "ISO", "", ""), (20408, "PySNMP Project", "", "")]
        source = iana_pen_to_mib.generate_mib_module(entries, module_name="TEST-PEN-MIB")
        assert "TEST-PEN-MIB" in source

    def test_generate_contains_enterprise_oids(self):
        entries = [(1, "ISO", "", ""), (20408, "PySNMP Project", "", "")]
        source = iana_pen_to_mib.generate_mib_module(entries)
        assert "(1, 3, 6, 1, 4, 1)" in source
        assert "(1,)" in source
        assert "(20408,)" in source

    def test_generate_contains_org_names(self):
        entries = [(1, "ISO", "", ""), (20408, "PySNMP Project", "", "")]
        source = iana_pen_to_mib.generate_mib_module(entries)
        assert "ISO" in source
        assert "PySNMP Project" in source

    def test_generate_skips_empty_orgs(self):
        entries = [(1, "", "", ""), (2, "IANA", "", "")]
        source = iana_pen_to_mib.generate_mib_module(entries)
        assert "IANA" in source
        # The empty-org entry should not produce a MibScalar
        assert "pen_1" not in source

    def test_generate_escapes_quotes(self):
        entries = [(1, "Builder's organization", "", "")]
        source = iana_pen_to_mib.generate_mib_module(entries)
        compile(source, "<test>", "exec")

    def test_generate_valid_python(self):
        """The generated source should be syntactically valid Python."""
        entries = [(1, "ISO", "", ""), (20408, "PySNMP Project", "", "")]
        source = iana_pen_to_mib.generate_mib_module(entries)
        # This should not raise SyntaxError
        compile(source, "<test>", "exec")

    def test_generated_module_loads_and_exports_instances(self, tmp_path):
        from pysnmp.smi.builder import DirMibSource, MibBuilder

        entries = [(1, "ISO", "", ""), (20408, "PySNMP Project", "", "")]
        module_name = "TEST-PEN-MIB"
        output = tmp_path / f"{module_name}.py"
        output.write_text(
            iana_pen_to_mib.generate_mib_module(entries, module_name=module_name),
            encoding="utf-8",
        )

        mib_builder = MibBuilder()
        mib_builder.addMibSources(DirMibSource(str(tmp_path)))
        mib_builder.loadModules(module_name)
        pen_1, pen_20408 = mib_builder.importSymbols(module_name, "pen_1", "pen_20408")

        assert pen_1.name == (1, 3, 6, 1, 4, 1, 1)
        assert str(pen_1.syntax) == "ISO"
        assert pen_20408.name == (1, 3, 6, 1, 4, 1, 20408)
        assert str(pen_20408.syntax) == "PySNMP Project"
