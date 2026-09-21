#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Benchmarks for the agent-side MIB instrumentation.

``MibInstrumController`` is the component an agent runs for every variable
of every incoming GET/GETNEXT/SET request.
"""
from pysnmp.smi import builder, instrum

SYSTEM_SCALARS = tuple(
    (1, 3, 6, 1, 2, 1, 1, column, 0) for column in (1, 2, 3, 4, 5, 6, 7)
)


def test_mib_instrum_controller_setup(benchmark):
    @benchmark
    def _():
        mibBuilder = builder.MibBuilder()
        mibBuilder.loadModules('SNMPv2-MIB', '__SNMPv2-MIB')
        instrum.MibInstrumController(mibBuilder)


def test_read_system_scalars(benchmark, mib_instrum_controller):
    varBinds = tuple((oid, None) for oid in SYSTEM_SCALARS)

    benchmark(mib_instrum_controller.readVars, varBinds)


def test_read_next_system_subtree(benchmark, mib_instrum_controller):
    """A GETNEXT sweep over the system group, as done by an SNMP walk."""
    @benchmark
    def _():
        varBinds = (((1, 3, 6, 1, 2, 1, 1), None),)
        for _unused in range(8):
            varBinds = tuple(
                (oid, None) for oid, _val in
                mib_instrum_controller.readNextVars(varBinds)
            )


def test_write_system_scalars(benchmark, mib_instrum_controller):
    varBinds = (
        ((1, 3, 6, 1, 2, 1, 1, 4, 0), 'admin@example.com'),
        ((1, 3, 6, 1, 2, 1, 1, 5, 0), 'edge-router-01'),
        ((1, 3, 6, 1, 2, 1, 1, 6, 0), 'Rack 42'),
    )

    benchmark(mib_instrum_controller.writeVars, varBinds)
