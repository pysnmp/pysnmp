## SNMP library for Python

[![PyPI](https://img.shields.io/pypi/v/pysnmplib.svg?maxAge=2592000)](https://pypi.python.org/pypi/pysnmplib)
[![Python Versions](https://img.shields.io/pypi/pyversions/pysnmplib.svg)](https://pypi.python.org/pypi/pysnmplib/)
[![CI](https://github.com/pysnmp/pysnmp/actions/workflows/build-test-release.yml/badge.svg)](https://github.com/pysnmp/pysnmp/actions/workflows/build-test-release.yml)
[![GitHub license](https://img.shields.io/badge/license-BSD-blue.svg)](https://raw.githubusercontent.com/pysnmp/pysnmp/main/LICENSE.rst)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://app.codspeed.io/pysnmp/pysnmp?utm_source=badge)

This is a pure-Python, open source and free implementation of v1/v2c/v3
SNMP engine distributed under 2-clause [BSD license](LICENSE.rst).

The PySNMP project was initially sponsored by a [PSF](http://www.python.org/psf/) grant.
Thank you!

This version is a fork of Ilya Etingof deceased's project [etingof/pysnmp](https://github.com/etingof/pysnmp). Ilya sadly passed away on 10-Aug-2022. Announcement [here](https://lists.openstack.org/pipermail/openstack-discuss/2022-August/030062.html). His work is still of great use to the Python community and he will be missed.

## Features

- Complete SNMPv1/v2c and SNMPv3 support
- SMI framework for resolving MIB information and implementing SMI
  Managed Objects
- Complete SNMP entity implementation
- USM Extended Security Options support (3DES, 192/256-bit AES encryption)
- Extensible network transports framework (UDP/IPv4, UDP/IPv6)
- [Asyncio](https://docs.python.org/3/library/asyncio.html) integration
- [pysmi](https://pysnmp.github.io/pysmi/) integration for dynamic MIB compilation
- Built-in instrumentation exposing protocol engine operations
- 100% Python, supports Python 3.10 and later
- MT-safe (if SnmpEngine is thread-local)

Features, specific to SNMPv3 model include:

- USM authentication (MD5/SHA-1/SHA-2) and privacy (DES/AES) protocols (RFC3414, RFC7860)
- View-based access control to use with any SNMP model (RFC3415)
- Built-in SNMP proxy PDU converter for building multi-lingual
  SNMP entities (RFC2576)
- Remote SNMP engine configuration
- Optional SNMP engine discovery
- Shipped with standard SNMP applications (RC3413)

## Download & Install

The PySNMP software is freely available for download from [PyPI](https://pypi.python.org/pypi/pysnmplib)
and [GitHub](https://github.com/pysnmp/pysnmp.git).

Just run:

```bash
$ pip install pysnmplib
```

That pulls in what an SNMP engine needs to run:

- [PyASN1](https://github.com/pysnmp/pyasn1)
- [PyCryptodomex](https://pycryptodome.readthedocs.io) (required for SNMPv3 encryption; imported lazily, so
  SNMPv1, SNMPv2c and the SNMPv3 noAuthNoPriv/authNoPriv security levels work without it)

[pysmi](https://pysnmp.github.io/pysmi/) is *not* pulled in. It compiles ASN.1 MIB
sources at run time, which some deployments do and most do not, so it is an extra:

```bash
$ pip install 'pysnmplib[compile]'
```

Without it everything except run-time MIB compilation works — including SNMPv3, name
resolution and the standard MIBs an engine needs, which PySNMP ships. Asking for a MIB
compiler when the extra is not installed raises `SmiError` naming the missing import.

MIB *content* is a separate thing again, and not a pip install: module
definitions come from the [MIB distribution](https://pysnmp.github.io/mibs/),
used live over HTTPS or installed locally from a release archive or an OCI
image. PySNMP starts without it, on the standard modules it ships.

## Examples

PySNMP is designed in a layered fashion. Top-level and easiest to use API is known as
_hlapi_. Here's a quick example on how to SNMP GET:

```python
from pysnmp.hlapi import *

iterator = getCmd(
    SnmpEngine(),
    CommunityData("public"),
    UdpTransportTarget(("localhost", 161)),
    ContextData(),
    ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
)

errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

if errorIndication:  # SNMP engine errors
    print(errorIndication)
else:
    if errorStatus:  # SNMP agent errors
        print(
            "%s at %s"
            % (
                errorStatus.prettyPrint(),
                varBinds[int(errorIndex) - 1] if errorIndex else "?",
            )
        )
    else:
        for varBind in varBinds:  # SNMP response contents
            print(" = ".join([x.prettyPrint() for x in varBind]))
```

This is how to send SNMP TRAP:

```python
from pysnmp.hlapi import *

errorIndication, errorStatus, errorIndex, varBinds = next(
    sendNotification(
        SnmpEngine(OctetString(hexValue="8000000001020304")),
        UsmUserData(
            "usr-sha-aes128",
            "authkey1",
            "privkey1",
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmAesCfb128Protocol,
        ),
        UdpTransportTarget(("localhost", 162)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity("SNMPv2-MIB", "authenticationFailure")),
    )
)

if errorIndication:
    print(errorIndication)
```

```bash
$ python3 examples/hlapi/asyncio/manager/cmdgen/v1-get.py
SNMPv2-MIB::sysDescr.0 = Linux localhost 5.15.0
$
$ python3 examples/hlapi/asyncio/agent/ntforg/default-v1-trap.py
SNMPv2-MIB::sysUpTime.0 = 0
SNMPv2-MIB::snmpTrapOID.0 = SNMPv2-MIB::warmStart
SNMPv2-MIB::sysName.0 = system name
```

Other than that, PySNMP is capable to automatically fetch and use required MIBs from HTTP, FTP sites
or local directories. You could configure any MIB source available to you (including
[the MIB distribution](https://pysnmp.github.io/mibs/)) for that purpose.

For more example scripts please refer to the `examples/` directory in this repository.

## Benchmarks

Performance of the protocol, security and MIB layers is tracked continuously
with [CodSpeed](https://app.codspeed.io/pysnmp/pysnmp). Every pull request from
a branch in this repository is measured against its base commit, so a
regression shows up on the pull request that causes it rather than after a
release.

Pull requests from forks are not measured. GitHub hands a fork's workflow a
restricted token that cannot mint the OpenID Connect identity the upload needs,
so the run would take the measurement and then fail to publish it. The job is
skipped instead, and a maintainer who wants the numbers for a fork's change can
get them by pushing the branch to this repository.

Measurements are taken under CPU simulation rather than by timing a wall
clock, so what is reported is work done and not how loaded the shared runner
happened to be. That is a different instrument from the wall-clock
[codec benchmark](docs/source/docs/codec-benchmark.rst), which compares this
library against net-snmp across platforms and interpreters and stays on-demand
for exactly that reason.

The suite lives in `benchmarks/` and is run with the project's own toolchain:

```bash
$ uv run --group bench pytest benchmarks/              # check they still work
$ uv run --group bench pytest benchmarks/ --codspeed   # measure them
```

## Documentation

The rendered documentation is at <https://pysnmp.github.io/pysnmp/>, built from
the `docs/` directory in this repository. The
[organization site](https://pysnmp.github.io/) describes how pysnmp, the MIB
distribution, pysmi and pyasn1 fit together.

If something does not work as expected, please
[open an issue](https://github.com/pysnmp/pysnmp/issues) at GitHub or
post your question [on Stack Overflow](https://stackoverflow.com/questions/tagged/pysnmp).

Bug reports and PRs are appreciated! ;-)

Copyright (c) 2005-2019, [Ilya Etingof deceased](https://lists.openstack.org/pipermail/openstack-discuss/2022-August/030062.html). All rights reserved.
