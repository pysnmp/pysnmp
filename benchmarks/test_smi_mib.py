#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Benchmarks for MIB loading, browsing and object resolution.

MIB handling dominates the start-up cost of any pysnmp application and,
through ``resolveWithMib()``, the cost of turning wire values into
human-readable ones.
"""
from pysnmp.smi import builder, indices, rfc1902, view

SYSTEM_SUBTREE = (1, 3, 6, 1, 2, 1, 1)

IF_TABLE_OIDS = [
    (1, 3, 6, 1, 2, 1, 2, 2, 1, column, index)
    for index in range(1, 26)
    for column in (1, 2, 3, 8, 10, 16)
]


def test_mib_builder_bootstrap(benchmark):
    """Creating a MibBuilder imports and instantiates the base MIB modules."""
    benchmark(builder.MibBuilder)


def test_load_standard_mib_modules(benchmark):
    @benchmark
    def _():
        mibBuilder = builder.MibBuilder()
        mibBuilder.loadModules(
            'SNMPv2-MIB', 'SNMP-FRAMEWORK-MIB', 'SNMP-TARGET-MIB',
            'SNMP-USER-BASED-SM-MIB', 'SNMP-VIEW-BASED-ACM-MIB',
        )


def test_mib_view_controller_index(benchmark, mib_builder):
    """Indexing the loaded modules is what the first lookup pays for."""
    @benchmark
    def _():
        mibViewController = view.MibViewController(mib_builder)
        mibViewController.getNodeName(SYSTEM_SUBTREE)


def test_get_node_name_by_oid(benchmark, mib_view_controller):
    @benchmark
    def _():
        for index in range(1, 8):
            mib_view_controller.getNodeNameByOid(SYSTEM_SUBTREE + (index,))


def test_get_node_name_by_desc(benchmark, mib_view_controller):
    @benchmark
    def _():
        for symbol in ('sysDescr', 'sysObjectID', 'sysUpTime',
                       'sysContact', 'sysName', 'sysLocation', 'sysServices'):
            mib_view_controller.getNodeNameByDesc(symbol, 'SNMPv2-MIB')


def test_walk_next_node_names(benchmark, mib_view_controller):
    """A MIB tree walk, the lookup pattern behind ``nextCmd()``."""
    @benchmark
    def _():
        nodeName = SYSTEM_SUBTREE
        for _unused in range(32):
            nodeName, _label, _suffix = mib_view_controller.getNextNodeName(
                nodeName
            )


def test_object_identity_resolve_by_symbol(benchmark, mib_view_controller):
    @benchmark
    def _():
        rfc1902.ObjectIdentity(
            'SNMPv2-MIB', 'sysDescr', 0
        ).resolveWithMib(mib_view_controller)


def test_object_identity_resolve_by_oid(benchmark, mib_view_controller):
    @benchmark
    def _():
        rfc1902.ObjectIdentity(
            '1.3.6.1.2.1.1.5.0'
        ).resolveWithMib(mib_view_controller)


def test_object_type_resolve_and_pretty_print(benchmark, mib_view_controller):
    @benchmark
    def _():
        objectType = rfc1902.ObjectType(
            rfc1902.ObjectIdentity('SNMPv2-MIB', 'sysUpTime', 0), 12345678
        )
        objectType.resolveWithMib(mib_view_controller)
        objectType.prettyPrint()


def test_oid_ordered_dict_populate(benchmark):
    @benchmark
    def _():
        oidDict = indices.OidOrderedDict()
        for idx, oid in enumerate(IF_TABLE_OIDS):
            oidDict[oid] = idx
        oidDict.keys()


def test_oid_ordered_dict_next_key(benchmark):
    oidDict = indices.OidOrderedDict()
    for idx, oid in enumerate(IF_TABLE_OIDS):
        oidDict[oid] = idx
    oidDict.keys()

    @benchmark
    def _():
        key = IF_TABLE_OIDS[0]
        for _unused in range(64):
            key = oidDict.nextKey(key)
