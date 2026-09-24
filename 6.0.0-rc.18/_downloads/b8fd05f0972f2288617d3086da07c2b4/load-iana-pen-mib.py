#!/usr/bin/env python3
"""
Load an IANA PEN MIB instance module
++++++++++++++++++++++++++++++++++++

Load a module produced by ``tools/iana_pen_to_mib.py`` and resolve one
private enterprise number to its registered organization name.

Run from the repository root after generating the module::

    python examples/smi/manager/load-iana-pen-mib.py \
        build/IANA-PEN-MIB.py 20408

"""  #

import argparse
from pathlib import Path

from pysnmp.smi.builder import DirMibSource, MibBuilder

parser = argparse.ArgumentParser()
parser.add_argument("mib", help="Generated IANA PEN MIB Python file")
parser.add_argument("pen", type=int, help="Private enterprise number to look up")
parser.add_argument(
    "--module-name",
    help="Generated module name (defaults to the input filename without .py)",
)
args = parser.parse_args()

mib_path = Path(args.mib).resolve()
module_name = args.module_name or mib_path.stem

mib_builder = MibBuilder()
mib_builder.addMibSources(DirMibSource(str(mib_path.parent)))
mib_builder.loadModules(module_name)

(pen_instance,) = mib_builder.importSymbols(module_name, f"pen_{args.pen}")
oid = ".".join(str(component) for component in pen_instance.name)
print(f"{oid} = {pen_instance.syntax.prettyPrint()}")
