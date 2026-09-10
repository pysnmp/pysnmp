#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""Resolving MIB names to OIDs and OIDs back to names.

`MibViewController` sits over a `MibBuilder` and indexes what it loaded, so a
caller can ask for `sysDescr` and get 1.3.6.1.2.1.1.1, ask the other way
round, or walk to the next object in OID order across every loaded module.
"""

from pysnmp import debug
from pysnmp.smi import error
from pysnmp.smi.indices import OidOrderedDict, OrderedDict

__all__ = ["MibViewController"]

classTypes = (type,)


class MibViewController:
    """Indexes what a builder loaded, and answers questions about names and OIDs.

    Resolves a label to an OID and back, and walks to the next object in OID
    order across every loaded module -- which is not the order the modules were
    loaded in, nor lexical order on their names.
    """

    def __init__(self, mibBuilder):
        """Indexing is deferred until the first lookup, as in the instrumentation."""
        self.mibBuilder = mibBuilder
        self.lastBuildId = -1
        self.__mibSymbolsIdx = OrderedDict()

        # OIDs a corpus has already been asked about and could not place, so
        # that a receiver hearing the same unknown trap every thirty seconds
        # asks once rather than every time. Bounded by the number of distinct
        # unresolvable prefixes a deployment actually sees, which is small.
        # Discarded when the builder is given a different corpus, since the
        # answer may well have changed.
        self.__corpusMisses = set()
        self.__corpusSeen = None

        # Resolved lazily, and only on the path that needs it -- importing a
        # symbol here would load SNMPv2-SMI when the controller is built,
        # which nothing else about it requires.
        self.__objectType = None

    # Indexing part

    def indexMib(self):
        """Rebuild the name and OID indices, unless nothing has been loaded since.

        Every lookup calls this first, so the builder's build counter is what keeps it
        from re-indexing on each one.
        """
        # A different corpus may well place an OID this one could not, so the
        # record of what it could not place does not outlive it.
        corpus = self.mibBuilder.getMibCorpus()

        if corpus is not self.__corpusSeen:
            self.__corpusSeen = corpus
            self.__corpusMisses.clear()

        if self.lastBuildId == self.mibBuilder.lastBuildId:
            return

        debug.logger & debug.flagMIB and debug.logger("indexMib: re-indexing MIB view")

        (MibScalarInstance,) = self.mibBuilder.importSymbols(
            "SNMPv2-SMI", "MibScalarInstance"
        )

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
        for modName in [""] + modNames:
            # Modules index
            self.__mibSymbolsIdx[modName] = mibMod = {
                "oidToLabelIdx": OidOrderedDict(),
                "labelToOidIdx": {},
                "varToNameIdx": {},
                "typeToModIdx": OrderedDict(),
                "oidToModIdx": {},
            }

            if not modName:
                globMibMod = mibMod
                continue

            # Types & MIB vars indices
            for n, v in self.mibBuilder.mibSymbols[modName].items():
                if n == self.mibBuilder.moduleID:  # do not index this
                    continue  # special symbol
                if isinstance(v, classTypes):
                    if n in mibMod["typeToModIdx"]:
                        raise error.SmiError(
                            "Duplicate SMI type {}::{}, has {}".format(
                                modName, n, mibMod["typeToModIdx"][n]
                            )
                        )
                    globMibMod["typeToModIdx"][n] = modName
                    mibMod["typeToModIdx"][n] = modName
                else:
                    if isinstance(v, MibScalarInstance):
                        continue
                    if n in mibMod["varToNameIdx"]:
                        raise error.SmiError(
                            "Duplicate MIB variable {}::{} has {}".format(
                                modName, n, mibMod["varToNameIdx"][n]
                            )
                        )
                    globMibMod["varToNameIdx"][n] = v.name
                    mibMod["varToNameIdx"][n] = v.name
                    # Potentionally ambiguous mapping ahead
                    globMibMod["oidToModIdx"][v.name] = modName
                    mibMod["oidToModIdx"][v.name] = modName
                    globMibMod["oidToLabelIdx"][v.name] = (n,)
                    mibMod["oidToLabelIdx"][v.name] = (n,)

        # Build oid->long-label index
        oidToLabelIdx = self.__mibSymbolsIdx[""]["oidToLabelIdx"]
        labelToOidIdx = self.__mibSymbolsIdx[""]["labelToOidIdx"]
        prevOid = ()
        baseLabel = ()
        for key in oidToLabelIdx:
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
            for oid in mibMod["oidToLabelIdx"]:
                mibMod["oidToLabelIdx"][oid] = oidToLabelIdx[oid]
                mibMod["labelToOidIdx"][oidToLabelIdx[oid]] = oid

        self.lastBuildId = self.mibBuilder.lastBuildId

    # Module management

    def getOrderedModuleName(self, index):
        """The loaded module at that position, counting from either end."""
        self.indexMib()
        modNames = self.__mibSymbolsIdx.keys()
        if modNames:
            return modNames[index]
        raise error.SmiError(f"No modules loaded at {self}")

    def getFirstModuleName(self):
        """The first loaded module."""
        return self.getOrderedModuleName(0)

    def getLastModuleName(self):
        """The last loaded module."""
        return self.getOrderedModuleName(-1)

    def getNextModuleName(self, modName):
        """The module after this one."""
        self.indexMib()
        try:
            return self.__mibSymbolsIdx.nextKey(modName)
        except KeyError as exc:
            raise error.SmiError(f"No module next to {modName} at {self}") from exc

    # MIB tree node management

    def __getOidLabel(self, nodeName, oidToLabelIdx, labelToOidIdx):
        """getOidLabel(nodeName) -> (oid, label, suffix)."""
        if not nodeName:
            return nodeName, nodeName, ()
        if nodeName in labelToOidIdx:
            return labelToOidIdx[nodeName], nodeName, ()
        if nodeName in oidToLabelIdx:
            return nodeName, oidToLabelIdx[nodeName], ()
        if len(nodeName) < 2:
            return nodeName, nodeName, ()
        oid, label, suffix = self.__getOidLabel(
            nodeName[:-1], oidToLabelIdx, labelToOidIdx
        )
        suffix = suffix + nodeName[-1:]
        resLabel = label + tuple(str(x) for x in suffix)
        if resLabel in labelToOidIdx:
            return labelToOidIdx[resLabel], resLabel, ()
        resOid = oid + suffix
        if resOid in oidToLabelIdx:
            return resOid, oidToLabelIdx[resOid], ()
        return oid, label, suffix

    def __worthAskingCorpus(self, oid, label, suffix, mibMod):
        """Whether an incomplete resolution is one a corpus could improve on.

        `__getOidLabel` always answers with the longest prefix it knows, so a
        miss is rarely total: an unknown vendor OID lands on ``enterprises``
        with the rest as suffix, exactly as a legitimate instance OID lands on
        its column. Telling those apart is what keeps this off the hot path.

        What separates them is the node the prefix resolved to. Below an
        `ObjectType` -- a scalar, a table, a row, a column -- the remaining
        arcs are instance arcs, the MIB says nothing further about them and no
        module could. Below a bare registration point -- `MibIdentifier`,
        `ObjectIdentity`, and the arcs under an unloaded vendor subtree -- the
        remaining arcs are unregistered territory, which is precisely where a
        module the corpus carries would sit.

        So a walk of ten thousand instance OIDs asks the corpus nothing, and
        an OID under an unloaded subtree asks once.
        """
        if not suffix:
            return False

        if oid == label:
            # Nothing resolved at all, so there is no node to classify.
            return True

        modName = mibMod["oidToModIdx"].get(oid)

        if modName is None:
            return True

        if self.__objectType is None:
            # ObjectType itself is not a symbol a MIB module exports, so the
            # three exported classes that descend from it stand in for it.
            # MibTableColumn is a MibScalar and needs no entry of its own.
            self.__objectType = self.mibBuilder.importSymbols(
                "SNMPv2-SMI", "MibScalar", "MibTable", "MibTableRow"
            )

        node = self.mibBuilder.mibSymbols.get(modName, {}).get(label[-1])

        return not isinstance(node, self.__objectType)

    def _corpusModuleFor(self, nodeName, modName):
        """Load the module a corpus says answers for an OID, if one does.

        The gap this closes: a corpus can resolve an arbitrary OID to a module
        by longest prefix, but until now nothing asked it to. A trap naming a
        module that is carried by the corpus and simply not loaded resolved to
        nothing, and the receiver saw raw arcs.

        Only for the merged view (``modName=""``). Asking a named module about
        an OID it does not carry is a different question, and loading some
        other module cannot answer it.

        Only for OIDs. A label tuple is not something a corpus indexes, and
        `getNodeName` reaches here with one on its way to trying the symbol
        form.

        Returns
        -------
            Whether a module was loaded, and so whether re-indexing and
            retrying is worth it.
        """
        if modName:
            return False

        corpus = self.mibBuilder.getMibCorpus()

        if corpus is None:
            return False

        try:
            arcs = tuple(int(x) for x in nodeName)

        except (TypeError, ValueError):
            return False

        if not arcs or arcs in self.__corpusMisses:
            return False

        # Recorded before the lookup, not after: a corpus that cannot place
        # this OID cannot place it on the next trap either, and a module that
        # fails to build should not be retried on every packet.
        self.__corpusMisses.add(arcs)

        found = corpus.find_module(arcs)

        if found is None or found in self.mibBuilder.mibSymbols:
            return False

        try:
            self.mibBuilder.loadModules(found)

        except error.SmiError:
            debug.logger & debug.flagMIB and debug.logger(
                f"_corpusModuleFor: corpus named {found} for {arcs} but it "
                f"could not be loaded"
            )
            return False

        debug.logger & debug.flagMIB and debug.logger(
            f"_corpusModuleFor: loaded {found} for {arcs} from the corpus"
        )

        return True

    def getNodeNameByOid(self, nodeName, modName=""):
        """Resolve an OID or a label to `(oid, label, suffix)`.

        An OID need not name an object exactly: the longest known prefix is what
        resolves, and the rest comes back as the suffix, which is how an instance under
        a column is named. An OID that resolves to nothing but itself is not in this
        MIB view at all -- unless a corpus can say which module would have carried it,
        in which case that module is loaded and the lookup is tried once more.
        """
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f"No module {modName} at {self}")
        oid, label, suffix = self.__getOidLabel(
            nodeName, mibMod["oidToLabelIdx"], mibMod["labelToOidIdx"]
        )
        if self.__worthAskingCorpus(oid, label, suffix, mibMod) and (
            self._corpusModuleFor(nodeName, modName)
        ):
            self.indexMib()
            mibMod = self.__mibSymbolsIdx[modName]
            oid, label, suffix = self.__getOidLabel(
                nodeName, mibMod["oidToLabelIdx"], mibMod["labelToOidIdx"]
            )
        if oid == label:
            raise error.NoSuchObjectError(
                str=f"Can't resolve node name {modName}::{nodeName} at {self}"
            )
        debug.logger & debug.flagMIB and debug.logger(
            f"getNodeNameByOid: resolved {modName}:{nodeName} -> {label}.{suffix}"
        )
        return oid, label, suffix

    def getNodeNameByDesc(self, nodeName, modName=""):
        """Resolve a MIB symbol's name to `(oid, label, suffix)`."""
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f"No module {modName} at {self}")
        if nodeName in mibMod["varToNameIdx"]:
            oid = mibMod["varToNameIdx"][nodeName]
        else:
            raise error.NoSuchObjectError(
                str=f"No such symbol {modName}::{nodeName} at {self}"
            )
        debug.logger & debug.flagMIB and debug.logger(
            f"getNodeNameByDesc: resolved {modName}:{nodeName} -> {oid}"
        )
        return self.getNodeNameByOid(oid, modName)

    def getNodeName(self, nodeName, modName=""):
        """Resolve either an OID, a label, or a `(symbol, index...)` tuple.

        The forms are tried in that order, since a caller may have any of the three and
        they cannot be told apart reliably by shape.
        """
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

    def getOrderedNodeName(self, index, modName="", nodeType=None):
        """The object at that position in the module, optionally of one node type."""
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f"No module {modName} at {self}")
        if not mibMod["oidToLabelIdx"]:
            raise error.NoSuchObjectError(
                str=f"No variables at MIB module {modName} at {self}"
            )
        if nodeType is not None:
            # Filter by node type (scalar, table, column, row)
            MibScalar, MibTable, MibTableColumn, MibTableRow = (
                self.mibBuilder.importSymbols(
                    "SNMPv2-SMI",
                    "MibScalar",
                    "MibTable",
                    "MibTableColumn",
                    "MibTableRow",
                )
            )
            nodeTypeMap = {
                "scalar": MibScalar,
                "table": MibTable,
                "column": MibTableColumn,
                "row": MibTableRow,
            }
            targetClass = nodeTypeMap.get(nodeType)
            if targetClass is None:
                raise error.SmiError(f"Unknown node type {nodeType!r} at {self}")
            filtered = []
            for oid, label in mibMod["oidToLabelIdx"].items():
                symName = label[-1]
                if symName in self.mibBuilder.mibSymbols[modName]:
                    symObj = self.mibBuilder.mibSymbols[modName][symName]
                    if isinstance(symObj, targetClass):
                        filtered.append((oid, label))
            if not filtered:
                raise error.NoSuchObjectError(
                    str=f"No {nodeType} nodes at MIB module {modName} at {self}"
                )
            try:
                if index < 0:
                    index += len(filtered)
                oid, label = filtered[index]
            except IndexError as exc:
                raise error.NoSuchObjectError(
                    str=f"No {nodeType} symbol at position {index} in MIB module {modName} at {self}"
                ) from exc
            return oid, label, ()
        try:
            oid, label = mibMod["oidToLabelIdx"].items()[index]
        except KeyError as exc:
            raise error.NoSuchObjectError(
                str=f"No symbol at position {index} in MIB module {modName} at {self}"
            ) from exc
        return oid, label, ()

    def getFirstNodeName(self, modName="", nodeType=None):
        """The first object in the module, or the first of one node type."""
        return self.getOrderedNodeName(0, modName, nodeType)

    def getLastNodeName(self, modName="", nodeType=None):
        """The last object in the module, or the last of one node type."""
        return self.getOrderedNodeName(-1, modName, nodeType)

    def getNextNodeName(self, nodeName, modName=""):
        """The object after this one, in OID order.

        OID order is neither the order the modules were loaded in nor lexical order on
        their names, which is why this cannot be answered from a plain mapping.
        """
        oid, label, suffix = self.getNodeName(nodeName, modName)
        try:
            return self.getNodeName(
                self.__mibSymbolsIdx[modName]["oidToLabelIdx"].nextKey(oid) + suffix,
                modName,
            )
        except KeyError as exc:
            raise error.NoSuchObjectError(
                str=f"No name next to {modName}::{nodeName} at {self}"
            ) from exc

    def getParentNodeName(self, nodeName, modName=""):
        """The object one level up, its last sub-identifier moved onto the suffix."""
        oid, label, suffix = self.getNodeName(nodeName, modName)
        if len(oid) < 2:
            raise error.NoSuchObjectError(
                str=f"No parent name for {modName}::{nodeName} at {self}"
            )
        return oid[:-1], label[:-1], oid[-1:] + suffix

    def getNodeLocation(self, nodeName, modName=""):
        """Which module defines an object, and under what label.

        The answer comes from the index across all modules rather than from any one of
        them, since the caller is asking precisely because they do not know which module
        it is in.
        """
        oid, label, suffix = self.getNodeName(nodeName, modName)
        return self.__mibSymbolsIdx[""]["oidToModIdx"][oid], label[-1], suffix

    # MIB type management

    def getTypeName(self, typeName, modName=""):
        """Which module defines a textual convention or type."""
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f"No module {modName} at {self}")
        if typeName in mibMod["typeToModIdx"]:
            m = mibMod["typeToModIdx"][typeName]
        else:
            raise error.NoSuchObjectError(
                str=f"No such type {modName}::{typeName} at {self}"
            )
        return m, typeName

    def getOrderedTypeName(self, index, modName=""):
        """The type at that position in the module, counting from either end."""
        self.indexMib()
        if modName in self.__mibSymbolsIdx:
            mibMod = self.__mibSymbolsIdx[modName]
        else:
            raise error.SmiError(f"No module {modName} at {self}")
        if not mibMod["typeToModIdx"]:
            raise error.NoSuchObjectError(
                str=f"No types at MIB module {modName} at {self}"
            )
        t = mibMod["typeToModIdx"].keys()[index]
        return mibMod["typeToModIdx"][t], t

    def getFirstTypeName(self, modName=""):
        """The first type the module defines."""
        return self.getOrderedTypeName(0, modName)

    def getLastTypeName(self, modName=""):
        """The last type the module defines."""
        return self.getOrderedTypeName(-1, modName)

    def getNextType(self, typeName, modName=""):
        """The type after this one."""
        m, t = self.getTypeName(typeName, modName)
        try:
            return self.__mibSymbolsIdx[m]["typeToModIdx"].nextKey(t)
        except KeyError as exc:
            raise error.NoSuchObjectError(
                str=f"No type next to {modName}::{typeName} at {self}"
            ) from exc

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
            is the ``MibTableColumn`` instance.
        :raises SmiError: if the module or symbol is not found.

        Examples
        --------
        >>> from pysnmp.smi import builder
        >>> mibBuilder = builder.MibBuilder()
        >>> mibView = MibViewController(mibBuilder)
        >>> cols = mibView.getTableColumns('SNMPv2-MIB', 'sysOREntry')
        >>> [(colId, colNode.getMaxAccess()) for colId, colName, colNode in cols]
        [(1, 'notaccessible'), (2, 'readonly'), (3, 'readonly'), (4, 'readonly')]

        Column 1 is ``sysORIndex``, the table's INDEX. RFC 3418 declares it
        not-accessible; this example said ``readonly`` while the base layer was
        a 2017 freeze that got it wrong (pysnmp/pysnmp#198).
        """
        (MibTableRow,) = self.mibBuilder.importSymbols("SNMPv2-SMI", "MibTableRow")
        (rowNode,) = self.mibBuilder.importSymbols(modName, rowSymName)
        if not isinstance(rowNode, MibTableRow):
            raise error.SmiError(
                f"Symbol {modName}::{rowSymName} is not a MibTableRow at {self}"
            )
        return rowNode.getColumns()

    def resolveCellOid(self, modName, rowSymName, column, *indices):
        """Resolve a table cell address into a full OID.

        :param modName: MIB module name.
        :param rowSymName: MIB symbol name of the table row/entry.
        :param column: Column symbol name or number (last sub-OID).
        :param indices: Typed index values (e.g. ``'my-router'`` or ``1``).
        :return: tuple of ints — the full OID identifying the cell.

        Examples
        --------
        >>> from pysnmp.smi import builder
        >>> mibBuilder = builder.MibBuilder()
        >>> mibView = MibViewController(mibBuilder)
        >>> oid = mibView.resolveCellOid('SNMP-COMMUNITY-MIB',
        ...                              'snmpCommunityEntry', 2, 'my-router')
        >>> oid
        (1, 3, 6, 1, 6, 3, 18, 1, 1, 1, 2, 109, 121, 45, 114, 111, 117, 116, 101, 114)
        """
        MibTableColumn, MibTableRow = self.mibBuilder.importSymbols(
            "SNMPv2-SMI", "MibTableColumn", "MibTableRow"
        )
        (rowNode,) = self.mibBuilder.importSymbols(modName, rowSymName)
        if not isinstance(rowNode, MibTableRow):
            raise error.SmiError(
                f"Symbol {modName}::{rowSymName} is not a MibTableRow at {self}"
            )

        if isinstance(column, str):
            (columnNode,) = self.mibBuilder.importSymbols(modName, column)
            if (
                not isinstance(columnNode, MibTableColumn)
                or columnNode.name[:-1] != rowNode.name
            ):
                raise error.SmiError(
                    f"Symbol {modName}::{column} is not a column of {rowSymName} at {self}"
                )
            column = columnNode.name[-1]

        return rowNode.getCellOid(column, *indices)

    def getTableCellInfo(self, cellOid):
        """Split a table cell OID into its MIB names and typed indices.

        :param cellOid: Complete table cell OID.
        :return: ``(moduleName, rowName, columnName, indices)``.
        :raises SmiError: if *cellOid* does not identify a table cell.
        """
        MibTableColumn, MibTableRow = self.mibBuilder.importSymbols(
            "SNMPv2-SMI", "MibTableColumn", "MibTableRow"
        )
        modName, columnName, suffix = self.getNodeLocation(tuple(cellOid))
        (columnNode,) = self.mibBuilder.importSymbols(modName, columnName)
        if not isinstance(columnNode, MibTableColumn):
            raise error.SmiError(
                f"OID {tuple(cellOid)!r} is not a table cell at {self}"
            )

        rowModName, rowName, rowSuffix = self.getNodeLocation(columnNode.name[:-1])
        (rowNode,) = self.mibBuilder.importSymbols(rowModName, rowName)
        if rowSuffix or not isinstance(rowNode, MibTableRow):
            raise error.SmiError(
                f"Column {modName}::{columnName} has no table row at {self}"
            )

        return modName, rowName, columnName, rowNode.getCellIndices(suffix)

    get_table_columns = getTableColumns
    resolve_cell_oid = resolveCellOid
    get_table_cell_info = getTableCellInfo
