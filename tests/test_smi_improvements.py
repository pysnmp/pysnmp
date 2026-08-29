"""Tests for Tier 4 SMI improvements: optional column support, table cell API, and clone/subtype documentation."""

import pytest

from pysnmp.smi.builder import MibBuilder
from pysnmp.smi.view import MibViewController
from pysnmp.proto.rfc1902 import Integer32, OctetString

# MibTableColumn and MibTableRow live in the hyphenated SNMPv2-SMI module,
# so we import them via MibBuilder.importSymbols.
_mibBuilder = MibBuilder()
MibTableColumn, MibTableRow = _mibBuilder.importSymbols(
    "SNMPv2-SMI", "MibTableColumn", "MibTableRow"
)


# ---- Optional column support (TODO #14) ----


class TestOptionalColumn:
    """Test the optional column flag on MibTableColumn."""

    def test_default_is_not_optional(self):
        col = MibTableColumn((1, 3, 6, 1, 2, 1, 10, 1), Integer32())
        assert not col.isOptional()
        assert col.optional is False

    def test_set_optional(self):
        col = MibTableColumn((1, 3, 6, 1, 2, 1, 10, 1), Integer32())
        col.setOptional()
        assert col.isOptional()
        assert col.optional is True

    def test_set_optional_false(self):
        col = MibTableColumn((1, 3, 6, 1, 2, 1, 10, 1), Integer32())
        col.setOptional(True)
        assert col.isOptional()
        col.setOptional(False)
        assert not col.isOptional()

    def test_set_optional_chaining(self):
        col = MibTableColumn((1, 3, 6, 1, 2, 1, 10, 1), Integer32())
        result = col.setOptional()
        assert result is col  # returns self for chaining

    def test_optional_column_in_write_commit(self):
        """Optional columns should not trigger InconsistentValueError."""
        # Build a minimal table row with one mandatory and one optional column
        row = MibTableRow((1, 3, 6, 1, 2, 1, 10, 1))
        row.setIndexNames((0, "SNMPv2-SMI", "Integer32"))

        col1 = MibTableColumn((1, 3, 6, 1, 2, 1, 10, 1, 1), Integer32())
        col1.setMaxAccess("read-create")
        col2 = MibTableColumn((1, 3, 6, 1, 2, 1, 10, 1, 2), Integer32())
        col2.setMaxAccess("read-create")
        col2.setOptional()  # This column is optional

        row.registerSubtrees(col1, col2)

        # The writeCommit check should skip the optional column
        # We can't easily test the full writeCommit without a full SNMP
        # engine, but we can verify the optional flag is accessible
        # on the registered column node.
        for mibNode in row._vars.values():
            if mibNode.name == col2.name:
                assert mibNode.isOptional()


# ---- Table cell mangling API (TODO #2) ----


class TestTableCellApi:
    """Test the table cell convenience methods on MibTableRow."""

    @pytest.fixture
    def mib_setup(self):
        from pysnmp.smi.instrum import MibInstrumController

        mibBuilder = MibBuilder()
        mibBuilder.loadModules("SNMPv2-MIB")
        # MibInstrumController indexes the MIB, registering columns to rows.
        # The indexing is lazy — trigger it with a read operation.
        ctrl = MibInstrumController(mibBuilder)
        ctrl.readVars([((1, 3, 6, 1, 2, 1, 1, 1, 0), None)])
        mvc = MibViewController(mibBuilder)
        return mibBuilder, mvc, ctrl

    def test_get_columns_returns_list(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        (sysOREntry,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")
        cols = sysOREntry.getColumns()
        assert isinstance(cols, list)
        # sysORTable has 4 columns: sysORIndex, sysORID, sysORDescr, sysORUpTime
        assert len(cols) >= 4

    def test_get_columns_structure(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        (sysOREntry,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")
        cols = sysOREntry.getColumns()
        for col_id, col_name, col_node in cols:
            assert isinstance(col_id, int)
            assert isinstance(col_name, tuple)
            # Check by class name since MibTableColumn from a different
            # MibBuilder instance is a different class object
            assert col_node.__class__.__name__ == "MibTableColumn"

    def test_get_cell_oid(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        (sysOREntry,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")
        # Build cell OID for sysORID (column 2) at index 1
        oid = sysOREntry.getCellOid(2, 1)
        # sysOREntry is at 1.3.6.1.2.1.1.9.1, column 2, index 1
        assert oid == (1, 3, 6, 1, 2, 1, 1, 9, 1, 2, 1)

    def test_get_row_oids(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        (sysOREntry,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")
        oids = sysOREntry.getRowOids(1)
        assert isinstance(oids, tuple)
        assert len(oids) >= 4  # at least 4 columns

    def test_get_cell_indices(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        (sysOREntry,) = mibBuilder.importSymbols("SNMPv2-MIB", "sysOREntry")
        # Encode index 1, then decode it back
        inst_id = sysOREntry.getInstIdFromIndices(1)
        indices = sysOREntry.getCellIndices(inst_id)
        assert len(indices) == 1
        assert int(indices[0]) == 1

    def test_get_table_columns_on_view(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        cols = mvc.getTableColumns("SNMPv2-MIB", "sysOREntry")
        assert isinstance(cols, list)
        assert len(cols) >= 4

    def test_resolve_cell_oid_on_view(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        oid = mvc.resolveCellOid("SNMPv2-MIB", "sysOREntry", 2, 1)
        assert oid == (1, 3, 6, 1, 2, 1, 1, 9, 1, 2, 1)

    def test_get_table_columns_non_row_raises(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        # sysDescr is a scalar, not a table row
        with pytest.raises(Exception):
            mvc.getTableColumns("SNMPv2-MIB", "sysDescr")

    def test_resolve_cell_oid_non_row_raises(self, mib_setup):
        mibBuilder, mvc, ctrl = mib_setup
        with pytest.raises(Exception):
            mvc.resolveCellOid("SNMPv2-MIB", "sysDescr", 0, 0)


# ---- clone() vs subtype() documentation (TODO #7) ----


class TestCloneSubtypeSemantics:
    """Verify that clone() and subtype() behave correctly per the documented guidelines.

    The guideline (documented in SNMPv2-SMI.py header):
      - subtype() for adding constraints (subtypeSpec=...)
      - clone() for everything else (value instantiation, namedValues, copying)
    """

    def test_clone_replaces_namedValues(self):
        """clone(namedValues=...) should replace, not concatenate."""
        from pyasn1.type.namedval import NamedValues

        original = Integer32().clone(namedValues=NamedValues(("a", 1), ("b", 2)))
        assert original.namedValues[1] == "a"
        assert original.namedValues[2] == "b"

        replaced = original.clone(namedValues=NamedValues(("c", 3)))
        assert replaced.namedValues[3] == "c"
        # The old namedValues should NOT be present
        assert 1 not in replaced.namedValues
        assert 2 not in replaced.namedValues

    def test_clone_sets_value(self):
        """clone(value) should set the value."""
        val = Integer32().clone(42)
        assert int(val) == 42

    def test_clone_no_args_copies(self):
        """clone() with no args should copy the current value."""
        val = Integer32().clone(42)
        copy = val.clone()
        assert int(copy) == 42

    def test_subtype_adds_constraints(self):
        """subtype(subtypeSpec=...) should intersect constraints."""
        from pyasn1.type.constraint import ValueRangeConstraint

        # Integer32 already has a base constraint; subtype should add to it
        constrained = Integer32().subtype(
            subtypeSpec=ValueRangeConstraint(0, 100)
        )
        # The constraint should be an intersection — values outside 0-100
        # should fail, and values outside Integer32 range should also fail
        assert int(constrained.clone(50)) == 50

        with pytest.raises(Exception):
            constrained.clone(200)  # outside the added range

    def test_chained_idiom(self):
        """The documented chained idiom: subtype → clone → clone."""
        from pyasn1.type.namedval import NamedValues
        from pyasn1.type.constraint import SingleValueConstraint

        # This is the standard MIB definition pattern
        result = (
            Integer32()
            .subtype(subtypeSpec=SingleValueConstraint(1, 2))
            .clone(namedValues=NamedValues(("up", 1), ("down", 2)))
            .clone(1)
        )
        assert int(result) == 1
        assert result.namedValues[1] == "up"
        assert result.namedValues[2] == "down"