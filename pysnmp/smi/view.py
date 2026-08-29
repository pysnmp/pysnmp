#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

from pysnmp import debug
from pysnmp.smi import error
from pysnmp.smi.indices import OidOrderedDict, OrderedDict

__all__ = ['MibViewController']

classTypes = (type,)
instanceTypes = (object,)


class MibViewController:
    def __init__(self, mibBuilder):
        self.mibBuilder = mibBuilder
        self.lastBuildId = -1
        self.__mibSymbolsIdx = OrderedDict()

    # Indexing part

    def indexMib(self):
        if self.lastBuildId == self.mibBuilder.lastBuildId:
            return

        debug.logger & debug.flagMIB and debug.logger('indexMib: re-indexing MIB view')

        (MibScalarInstance,) = self.mibBuilder.importSymbols('SNMPv2-SMI', 'MibScalarInstance')

        #
        # Create indices
        #

        # Module name -> module-scope indices
        self.__mibSymbolsIdx.clear()

        # Oid <-> label indices

        # This is potentially ambiguous mapping. Sort modules in
        # ascending age for resolution
        def __sortFun(x, b=self.mibBuilder):
            if b.moduleID in b.mibSymbols[x]:
                m = b.mibSymbols[x][b.moduleID]
                r = m.getRevisions()
                if r:
                    return r[0]

            return "1970-01-01 00:00"

        modNames = list(self.mibBuilder.mibSymbols.keys())
        modNames.sort(key=__sortFun)

        # Index modules names
        for modName in [''] + modNames:
            # Modules index
            self.__mibSymbolsIdx[modName] = mibMod = {
                'oidToLabelIdx': OidOrderedDict(),
                'labelToOidIdx': {},
                'varToNameIdx': {},
                'typeToModIdx': OrderedDict(),
                'oidToModIdx': {},
            }

            if not modName:
                globMibMod = mibMod
                continue

            # Types & MIB vars indices
            for n, v in self.mibBuilder.mibSymbols[modName].items():
                if n == self.mibBuilder.moduleID:  # do not index this
                    continue  # special symbol
                if isinstance(v, classTypes):
                    if n in mibMod['typeToModIdx']:
                        raise error.SmiError(
                            'Duplicate SMI type {}::{}, has {}'.format(
                                modName, n, mibMod['typeToModIdx'][n]
                            )
                        )
                    globMibMod['typeToModIdx'][n] = modName
                    mibMod['typeToModIdx'][n] = modName
                elif isinstance(v, instanceTypes):
                    if isinstance(v, MibScalarInstance):
                        continue
                    if n in mibMod['varToNameIdx']:
                        raise error.SmiError(
                            'Duplicate MIB variable {}::{} has {}'.format(
                                modName, n, mibMod['varToNameIdx'][n]
                            )
                        )
                    globMibMod['varToNameIdx'][n] = v.name
                    mibMod['varToNameIdx'][n] = v.name
                    # Potentionally ambiguous mapping ahead
                    globMibMod['oidToModIdx'][v.name] = modName
                    mibMod['oidToModIdx'][v.name] = modName
                    globMibMod['oidToLabelIdx'][v.name] = (n,)
                    mibMod['oidToLabelIdx'][v.name] = (n,)
                else:
                    raise error.SmiError(f'Unexpected object {modName}::{n}')

        # Build oid->long-label index
        oidToLabelIdx = self.__mibSymbolsIdx['']['oidToLabelIdx']
        labelToOidIdx = self.__mibSymbolsIdx['']['labelToOidIdx']
        prevOid = ()
        baseLabel = ()
        for key in oidToLabelIdx.keys():
            keydiff = len(key) - len(prevOid)
            if keydiff > 0:
                if prevOid:
                    if keydiff == 1:
                        baseLabel = oidToLabelIdx[prevOid]
                    else:
                        baseLabel += key[-keydiff:-1]
                else:
                    baseLabel = ()
            elif keydiff < 0:
                baseLabel = ()
                keyLen = len(key)
                i = keyLen - 1
                while i:
                    k = key[:i]
                    if k in oidToLabelIdx:
                        baseLabel = oidToLabelIdx[k]
                        if i != keyLen - 1:
                            baseLabel += key[i:-1]
                        break
                    i -= 1
            # Build oid->long-label index
            oidToLabelIdx[key] = baseLabel + oidToLabelIdx[key]
            # Build label->oid index
            labelToOidIdx[oidToLabelIdx[key]] = key
            prevOid = key

        # Build module-scope oid->long-label index
        for mibMod in self.__mibSymbolsIdx.values():
            for oid in mibMod['oidToLabelIdx'].keys():
                mibMod['oidToLabelIdx'][oid] = oidToLabelIdx[oid]
                mibMod['labelToOidIdx'][oidToLabelIdx[oid]] = oid

        self.lastBuildId = self.mibBuilder.lastBuildId

    # Module management

    def getOrderedModuleName(self, index):
        self.indexMib()
        modNames = self.__mibSymbolsIdx.keys()
        if modNames:
            return modNames[index]
        raise error.SmiError('No modules loaded at %s' % self)

    def getFirstModuleName(self):
        return self.getOrderedModuleName(0)

    def getLastModuleName(self):
        return self.getOrderedModuleName(-1)

    def getNextModuleName(self, modName):
        self.indexMib()
        try:
            return self.__mibSymbolsIdx.nextKey(modName)
        except KeyError:
            raise error.SmiError(f'No module next to {modName} at {self}')

    # MIB tree node management

    def __getOidLabel(self, nodeName, oidToLabelIdx, labelToOidIdx):
        """getOidLabel(nodeName) -> (oid, label, suffix)"""
        if not nodeName:
            return nodeName, nodeName, ()
        if nodeName in labelToOidIdx:
            return labelToOidIdx[nodeName], nodeName, ()
        if nodeName in oidToLabelIdx:
            return nodeName, oidToLabelIdx[nodeName], ()
        if len(nodeName) < 2:
            return nodeName, nodeName, ()
        oid, label, suffix = self.__getOidLabel(nodeName[:-1], oidToLabelIdx, labelToOidIdx)
        suffix = suffix + nodeName[-1:]
        resLabel = label + tuple(str(x) for x in suffix)
        if resLabel in labelToOidIdx:
            return labelToOidIdx[resLabel], resLabel, ()
        resOid = oid + suffix
        if resOid in oidToLabelIdx:
            return resOid, oidToLabelIdx[resOid], ()
        return oid, label, suffix

    def getNodeNameByOid(self, nodeName, modName=''):
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f'No module {modName} at {self}')
        oid, label, suffix = self.__getOidLabel(
            nodeName, mibMod['oidToLabelIdx'], mibMod['labelToOidIdx']
        )
        if oid == label:
            raise error.NoSuchObjectError(
                str='Can\'t resolve node name {}::{} at {}'.format(modName, nodeName, self)
            )
        debug.logger & debug.flagMIB and debug.logger(
            f'getNodeNameByOid: resolved {modName}:{nodeName} -> {label}.{suffix}'
        )
        return oid, label, suffix

    def getNodeNameByDesc(self, nodeName, modName=''):
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f'No module {modName} at {self}')
        if nodeName in mibMod['varToNameIdx']:
            oid = mibMod['varToNameIdx'][nodeName]
        else:
            raise error.NoSuchObjectError(str=f'No such symbol {modName}::{nodeName} at {self}')
        debug.logger & debug.flagMIB and debug.logger(
            f'getNodeNameByDesc: resolved {modName}:{nodeName} -> {oid}'
        )
        return self.getNodeNameByOid(oid, modName)

    def getNodeName(self, nodeName, modName=''):
        # nodeName may be either an absolute OID/label or a
        # ( MIB-symbol, su, ff, ix)
        try:
            # First try nodeName as an OID/label
            return self.getNodeNameByOid(nodeName, modName)
        except error.NoSuchObjectError:
            # ...on failure, try as MIB symbol
            oid, label, suffix = self.getNodeNameByDesc(nodeName[0], modName)
            # ...with trailing suffix
            return self.getNodeNameByOid(oid + suffix + nodeName[1:], modName)

    def getOrderedNodeName(self, index, modName='', nodeType=None):
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f'No module {modName} at {self}')
        if not mibMod['oidToLabelIdx']:
            raise error.NoSuchObjectError(str=f'No variables at MIB module {modName} at {self}')
        if nodeType is not None:
            # Filter by node type (scalar, table, column, row)
            MibScalar, MibTable, MibTableColumn, MibTableRow = self.mibBuilder.importSymbols(
                'SNMPv2-SMI', 'MibScalar', 'MibTable', 'MibTableColumn', 'MibTableRow'
            )
            nodeTypeMap = {
                'scalar': MibScalar,
                'table': MibTable,
                'column': MibTableColumn,
                'row': MibTableRow,
            }
            targetClass = nodeTypeMap.get(nodeType)
            if targetClass is None:
                raise error.SmiError(f'Unknown node type {nodeType!r} at {self}')
            filtered = []
            for oid, label in mibMod['oidToLabelIdx'].items():
                symName = label[-1]
                if symName in self.mibBuilder.mibSymbols[modName]:
                    symObj = self.mibBuilder.mibSymbols[modName][symName]
                    if isinstance(symObj, targetClass):
                        filtered.append((oid, label))
            if not filtered:
                raise error.NoSuchObjectError(
                    str=f'No {nodeType} nodes at MIB module {modName} at {self}'
                )
            try:
                if index < 0:
                    index += len(filtered)
                oid, label = filtered[index]
            except IndexError:
                raise error.NoSuchObjectError(
                    str=f'No {nodeType} symbol at position {index} in MIB module {modName} at {self}'
                )
            return oid, label, ()
        try:
            oid, label = mibMod['oidToLabelIdx'].items()[index]
        except KeyError:
            raise error.NoSuchObjectError(
                str=f'No symbol at position {index} in MIB module {modName} at {self}'
            )
        return oid, label, ()

    def getFirstNodeName(self, modName='', nodeType=None):
        return self.getOrderedNodeName(0, modName, nodeType)

    def getLastNodeName(self, modName='', nodeType=None):
        return self.getOrderedNodeName(-1, modName, nodeType)

    def getNextNodeName(self, nodeName, modName=''):
        oid, label, suffix = self.getNodeName(nodeName, modName)
        try:
            return self.getNodeName(
                self.__mibSymbolsIdx[modName]['oidToLabelIdx'].nextKey(oid) + suffix, modName
            )
        except KeyError:
            raise error.NoSuchObjectError(str=f'No name next to {modName}::{nodeName} at {self}')

    def getParentNodeName(self, nodeName, modName=''):
        oid, label, suffix = self.getNodeName(nodeName, modName)
        if len(oid) < 2:
            raise error.NoSuchObjectError(
                str='No parent name for {}::{} at {}'.format(modName, nodeName, self)
            )
        return oid[:-1], label[:-1], oid[-1:] + suffix

    def getNodeLocation(self, nodeName, modName=''):
        oid, label, suffix = self.getNodeName(nodeName, modName)
        return self.__mibSymbolsIdx['']['oidToModIdx'][oid], label[-1], suffix

    # MIB type management

    def getTypeName(self, typeName, modName=''):
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f'No module {modName} at {self}')
        if typeName in mibMod['typeToModIdx']:
            m = mibMod['typeToModIdx'][typeName]
        else:
            raise error.NoSuchObjectError(str=f'No such type {modName}::{typeName} at {self}')
        return m, typeName

    def getOrderedTypeName(self, index, modName=''):
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f'No module {modName} at {self}')
        if not mibMod['typeToModIdx']:
            raise error.NoSuchObjectError(str=f'No types at MIB module {modName} at {self}')
        t = mibMod['typeToModIdx'].keys()[index]
        return mibMod['typeToModIdx'][t], t

    def getFirstTypeName(self, modName=''):
        return self.getOrderedTypeName(0, modName)

    def getLastTypeName(self, modName=''):
        return self.getOrderedTypeName(-1, modName)

    def getNextType(self, typeName, modName=''):
        m, t = self.getTypeName(typeName, modName)
        try:
            return self.__mibSymbolsIdx[m]['typeToModIdx'].nextKey(t)
        except KeyError:
            raise error.NoSuchObjectError(str=f'No type next to {modName}::{typeName} at {self}')

    # ---- Table cell mangling API (TODO #2) ----
    # Convenience methods for table-level introspection that clearly separate
    # MIB module name, MIB object (table/row/column) name, and instance.

    def getTableColumns(self, modName, rowSymName):
        """Return column metadata for a MIB table row.

        :param modName: MIB module name (e.g. ``'SNMPv2-MIB'``).
        :param rowSymName: MIB symbol name of the table row/entry
            (e.g. ``'sysOREntry'``).
        :return: list of ``(colId, colName, colNode)`` tuples — one per
            column in the row.  ``colId`` is the column number (last
            sub-OID), ``colName`` is the full OID tuple, and ``colNode``
            is the :class:`MibTableColumn` instance.
        :raises SmiError: if the module or symbol is not found.

        Examples
        --------
        >>> mibView = MibViewController(mibBuilder)
        >>> cols = mibView.getTableColumns('SNMPv2-MIB', 'sysOREntry')
        >>> for colId, colName, colNode in cols:
        ...     print(colId, colNode.getMaxAccess())
        """
        (rowNode,) = self.mibBuilder.importSymbols(modName, rowSymName)
        if not hasattr(rowNode, 'getColumns'):
            raise error.SmiError(
                f'Symbol {modName}::{rowSymName} is not a MibTableRow at {self}'
            )
        return rowNode.getColumns()

    def resolveCellOid(self, modName, rowSymName, colId, *indices):
        """Resolve a table cell address into a full OID.

        :param modName: MIB module name.
        :param rowSymName: MIB symbol name of the table row/entry.
        :param colId: Column number (last sub-OID of the column).
        :param indices: Typed index values (e.g. ``'my-router'`` or ``1``).
        :return: tuple of ints — the full OID identifying the cell.

        Examples
        --------
        >>> oid = mibView.resolveCellOid('SNMP-COMMUNITY-MIB',
        ...                              'snmpCommunityEntry', 2, 'my-router')
        """
        (rowNode,) = self.mibBuilder.importSymbols(modName, rowSymName)
        if not hasattr(rowNode, 'getCellOid'):
            raise error.SmiError(
                f'Symbol {modName}::{rowSymName} is not a MibTableRow at {self}'
            )
        return rowNode.getCellOid(colId, *indices)
