#!/usr/bin/env python3
#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
# This tool parses IANA Private Enterprise Numbers (PEN) registry data
# and generates a pysnmp MIB instance module mapping enterprise numbers
# to organization names.
#
# The IANA PEN registry is published at:
#   https://www.iana.org/assignments/enterprise-numbers.txt
#
# Usage:
#   python tools/iana_pen_to_mib.py [--input FILE | --url URL] --output FILE
#
# The generated MIB module can be loaded by MibBuilder.load_modules().
#
"""Parse IANA Private Enterprise Numbers and generate a pysnmp MIB module.

The IANA PEN registry maps integer enterprise numbers to organization
names.  This tool reads the registry (from a local file or the IANA
website) and produces a Python MIB module file that defines a scalar
MIB object for each enterprise number under the
``1.3.6.1.4.1.<enterprise_number>`` OID, with the organization name as
the value.

The generated file uses standard pysnmp SMI classes and can be loaded
by ``MibBuilder.load_modules()`` just like any other compiled MIB
module.

Examples
--------
Download from IANA and generate a MIB module::

    $ python tools/iana_pen_to_mib.py --url \\
        https://www.iana.org/assignments/enterprise-numbers.txt \\
        --output IANA-PEN-MIB.py

Parse a local copy::

    $ python tools/iana_pen_to_mib.py --input enterprise-numbers.txt \\
        --output IANA-PEN-MIB.py

"""

from __future__ import annotations

import argparse
import sys
import urllib.request

__all__ = ["parse_iana_pen", "generate_mib_module"]

# The IANA PEN registry format is a text file where each entry consists
# of four consecutive lines:
#   1. Enterprise number (integer)
#   2. Organization name
#   3. Contact person
#   4. Email address
#
# Blank lines separate entries.  Some entries may have missing fields.

IANA_PEN_URL = "https://www.iana.org/assignments/enterprise-numbers.txt"


def parse_iana_pen(text: str) -> list[tuple[int, str, str, str]]:
    """Parse IANA PEN registry text into a list of entries.

    Parameters
    ----------
    text : str
        Raw text of the IANA PEN registry.

    Returns
    -------
    list of (int, str, str, str)
        Each tuple is ``(enterprise_number, organization, contact, email)``.
        Missing fields are empty strings.
    """
    entries = []
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # The enterprise number should be the first token on the line.
        # In the standard IANA format, the number is alone on its line.
        # Some exports may have the org name on the same line.
        parts = line.split(None, 1)
        if not parts or not parts[0].isdigit():
            i += 1
            continue

        enterprise_number = int(parts[0])
        organization = ""
        contact = ""
        email = ""
        consumed = 1  # the number line itself

        if len(parts) > 1:
            # Org name is on the same line as the number
            organization = parts[1].strip()
            # Read up to 2 more lines for contact, email
            for j in range(1, 3):
                if i + j < len(lines):
                    next_line = lines[i + j].strip()
                    if next_line:
                        parts2 = next_line.split(None, 1)
                        if not parts2[0].isdigit():
                            if j == 1:
                                contact = next_line
                                consumed = 2
                            elif j == 2:
                                email = next_line
                                consumed = 3
                        else:
                            break
                    else:
                        break
                else:
                    break
            i += consumed
        else:
            # Number is alone — read up to 3 more lines for org, contact, email
            for j in range(1, 4):
                if i + j < len(lines):
                    next_line = lines[i + j].strip()
                    if next_line:
                        parts2 = next_line.split(None, 1)
                        if not parts2[0].isdigit():
                            if j == 1:
                                organization = next_line
                                consumed = 2
                            elif j == 2:
                                contact = next_line
                                consumed = 3
                            elif j == 3:
                                email = next_line
                                consumed = 4
                        else:
                            break
                    else:
                        break
                else:
                    break
            i += consumed

        entries.append((enterprise_number, organization, contact, email))

        # Skip any trailing blank lines
        while i < len(lines) and not lines[i].strip():
            i += 1

    return entries


def generate_mib_module(
    entries: list[tuple[int, str, str, str]],
    module_name: str = "IANA-PEN-MIB",
) -> str:
    """Generate a pysnmp MIB module Python source from IANA PEN entries.

    Parameters
    ----------
    entries : list of (int, str, str, str)
        Parsed IANA PEN entries from :func:`parse_iana_pen`.

    module_name : str
        Name for the generated MIB module.

    Returns
    -------
    str
        Python source code for the MIB module.
    """
    lines = [
        "#",
        f"# Generated by iana_pen_to_mib.py — {module_name}",
        "# Maps IANA Private Enterprise Numbers to organization names.",
        "#",
        "# This file is auto-generated. Do not edit by hand.",
        "#",
        f"# PySNMP MIB module: {module_name}",
        "#",
        "# This file is designed to be loaded by MibBuilder.loadModules().",
        "# It uses the `mibBuilder` global that MibBuilder injects at load time.",
        "#",
        "(MibScalarInstance,) = mibBuilder.importSymbols(",
        '    "SNMPv2-SMI", "MibScalarInstance"',
        ")",
        "(DisplayString,) = mibBuilder.importSymbols(",
        '    "SNMPv2-TC", "DisplayString"',
        ")",
        "",
    ]

    used_names: set[str] = set()
    export_names: list[str] = []

    for enterprise_number, organization, _contact, _email in entries:
        if not organization:
            continue

        # Build a valid Python symbol name
        base_name = f"pen_{enterprise_number}"
        sym_name = base_name
        counter = 1
        while sym_name in used_names:
            sym_name = f"{base_name}_{counter}"
            counter += 1
        used_names.add(sym_name)
        export_names.append(sym_name)

        lines.append(f"_{sym_name} = MibScalarInstance(")
        lines.append("    (1, 3, 6, 1, 4, 1),")
        lines.append(f"    ({enterprise_number},),")
        lines.append(f"    DisplayString({organization!r}),")
        lines.append(")")
        lines.append("")

    lines.append("mibBuilder.exportSymbols(")
    lines.append(f"    {module_name!r},")
    for sym_name in export_names:
        lines.append(f"    {sym_name}=_{sym_name},")
    lines.append(")")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Parse IANA Private Enterprise Numbers and generate a pysnmp MIB module."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--input",
        metavar="FILE",
        help="Local file containing IANA PEN registry data.",
    )
    group.add_argument(
        "--url",
        metavar="URL",
        default=IANA_PEN_URL,
        help=f"URL to download IANA PEN registry from (default: {IANA_PEN_URL}).",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        required=True,
        help="Output Python MIB module file path.",
    )
    parser.add_argument(
        "--module-name",
        default="IANA-PEN-MIB",
        help="Name for the generated MIB module (default: IANA-PEN-MIB).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of entries to process (0 = all, for testing).",
    )

    args = parser.parse_args()

    # Read input data
    if args.input:
        with open(args.input, encoding="utf-8", errors="replace") as f:
            text = f.read()
    else:
        print(f"Downloading IANA PEN registry from {args.url}...", file=sys.stderr)
        with urllib.request.urlopen(args.url) as response:  # noqa: S310
            text = response.read().decode("utf-8", errors="replace")

    # Parse entries
    entries = parse_iana_pen(text)
    print(f"Parsed {len(entries)} entries.", file=sys.stderr)

    if args.limit > 0:
        entries = entries[: args.limit]
        print(f"Limited to {len(entries)} entries.", file=sys.stderr)

    # Generate MIB module
    source = generate_mib_module(entries, module_name=args.module_name)

    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(source)

    print(f"Wrote MIB module to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
