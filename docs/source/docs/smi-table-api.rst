SMI table construction and cell addressing
==========================================

PySNMP exposes helpers for constructing table cell OIDs, decomposing cell
OIDs into MIB symbols and typed indices, and declaring columns that may be
unset when a conceptual row becomes active.

Addressing table cells
----------------------

Create a :class:`~pysnmp.smi.view.MibViewController` from a MIB builder and
load the module that defines the table. These operations do not require an
instrumentation controller or an SNMP engine::

    from pysnmp.smi import builder, view

    mibBuilder = builder.MibBuilder()
    mibBuilder.loadModules('SNMPv2-MIB')
    mibView = view.MibViewController(mibBuilder)

    columns = mibView.get_table_columns('SNMPv2-MIB', 'sysOREntry')
    for columnId, columnOid, columnNode in columns:
        print(columnId, columnOid, columnNode.getMaxAccess())

    cellOid = mibView.resolve_cell_oid(
        'SNMPv2-MIB', 'sysOREntry', 'sysORID', 7
    )

The column can be identified by its MIB symbol, as above, or by its numeric
sub-identifier. Unknown columns and an incorrect number of index values raise
:class:`~pysnmp.smi.error.SmiError` rather than producing an invalid OID.

To split a complete cell OID back into its components::

    moduleName, rowName, columnName, indices = mibView.get_table_cell_info(
        cellOid
    )

    assert moduleName == 'SNMPv2-MIB'
    assert rowName == 'sysOREntry'
    assert columnName == 'sysORID'
    assert int(indices[0]) == 7

The decoded index values retain their MIB syntax. This matters for string,
object identifier, implied, and multi-part table indices.

The row object offers the corresponding lower-level operations:

``get_columns()``
    Return ``(column ID, column OID, column node)`` records in OID order.

``get_cell_oid(column_id, *indices)``
    Construct and validate one cell OID.

``get_row_oids(*indices)``
    Construct cell OIDs for every column in the row.

``get_cell_indices(instance_suffix)``
    Decode an instance suffix into typed index values.

The original camel-case spellings remain available for compatibility, such
as ``getTableColumns()`` and ``resolveCellOid()``. See the complete
:download:`table cell example </../../examples/smi/manager/table-cell-api.py>`.

Optional columns during row activation
--------------------------------------

When a ``RowStatus`` value activates a row, PySNMP normally requires every
column instance to have a value. A Python MIB definition can explicitly mark
a column that is allowed to remain unset::

    optionalValue = MibTableColumn(
        entryOid + (2,), DisplayString()
    ).setMaxAccess('read-create').set_optional()

``set_optional()`` only changes the row consistency check. It does not assign
a default value, make an index optional, or change access control. Columns
that are required by the MIB specification should retain the default
mandatory behavior. ``setOptional()`` and ``isOptional()`` are retained as
camel-case aliases.

MIB compilers cannot reliably infer optionality from descriptive ASN.1 text,
so compiled Python MIB modules must apply this marker where the MIB's row
creation rules permit an absent value.

Choosing ``clone`` or ``subtype``
---------------------------------

PyASN1 objects are immutable. Use ``subtype()`` when adding constraints or
ASN.1 tags, and use ``clone()`` when assigning a value or replacing an
attribute such as ``namedValues``::

    state = (
        Integer32()
        .subtype(subtypeSpec=SingleValueConstraint(1, 2))
        .clone(namedValues=NamedValues(('up', 1), ('down', 2)))
        .clone(1)
    )

Calling ``clone()`` without changes returns the same immutable object. It is
therefore safe to use when a caller only needs the current value, but it does
not guarantee a distinct Python object.
