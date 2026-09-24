#!/usr/bin/env python3
"""
Load generated MIB instance stubs
+++++++++++++++++++++++++++++++++

Load a MIB definition and its companion module produced by
``tools/mib_instance_generator.py``, then display all generated instances.

Run from the repository root::

    python examples/smi/agent/load-generated-mib-instances.py \
        EXAMPLE-DEVICE-MIB build/EXAMPLE-DEVICE-MIB_instances.py

"""  #

import argparse
from pathlib import Path

from pysnmp.smi.builder import DirMibSource, MibBuilder

parser = argparse.ArgumentParser()
parser.add_argument("definitions_module", help="Compiled MIB definitions module name")
parser.add_argument("instances", help="Generated MIB instances Python file")
parser.add_argument(
    "--mib-source",
    action="append",
    default=[],
    help="Additional directory containing compiled MIB definitions",
)
parser.add_argument(
    "--instances-module",
    help="Exported instances module name (defaults to <definitions>_instances)",
)
args = parser.parse_args()

instances_path = Path(args.instances).resolve()
instances_module = args.instances_module or f"{args.definitions_module}_instances"

mib_builder = MibBuilder()
for source in [instances_path.parent, *(Path(path) for path in args.mib_source)]:
    mib_builder.addMibSources(DirMibSource(str(source.resolve())))

mib_builder.loadModules(args.definitions_module)
mib_builder.loadModules(instances_path.stem)

for symbol_name, instance in sorted(mib_builder.mibSymbols[instances_module].items()):
    print(f"{symbol_name}: {instance.name} = {instance.syntax.prettyPrint()}")
