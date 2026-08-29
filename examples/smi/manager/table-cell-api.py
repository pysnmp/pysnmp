"""
Addressing and decomposing SMI table cells
++++++++++++++++++++++++++++++++++++++++++

Load a MIB, enumerate a conceptual row's columns, construct a cell OID from
symbolic names and typed indices, then decompose it back into those parts.
No SNMP engine or network connection is required.
"""  #

from pysnmp.smi import builder, view

mibBuilder = builder.MibBuilder()
mibBuilder.loadModules('SNMPv2-MIB')
mibView = view.MibViewController(mibBuilder)

print('sysORTable columns:')
for columnId, columnOid, columnNode in mibView.get_table_columns(
    'SNMPv2-MIB', 'sysOREntry'
):
    print(columnId, '.'.join(str(part) for part in columnOid), columnNode.getMaxAccess())

cellOid = mibView.resolve_cell_oid('SNMPv2-MIB', 'sysOREntry', 'sysORID', 7)
print('Cell OID:', '.'.join(str(part) for part in cellOid))

moduleName, rowName, columnName, indices = mibView.get_table_cell_info(cellOid)
print('Cell name:', f'{moduleName}::{rowName}::{columnName}')
print('Indices:', ', '.join(index.prettyPrint() for index in indices))
