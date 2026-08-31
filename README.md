## SNMP library for Python

[![PyPI](https://img.shields.io/pypi/v/pysnmplib.svg?maxAge=2592000)](https://pypi.python.org/pypi/pysnmplib)
[![Python Versions](https://img.shields.io/pypi/pyversions/pysnmplib.svg)](https://pypi.python.org/pypi/pysnmplib/)
[![CI](https://github.com/pysnmp/pysnmp/actions/workflows/build-test-release.yml/badge.svg)](https://github.com/pysnmp/pysnmp/actions/workflows/build-test-release.yml)
[![GitHub license](https://img.shields.io/badge/license-BSD-blue.svg)](https://raw.githubusercontent.com/pysnmp/pysnmp/main/LICENSE.rst)

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
- [PySMI](https://github.com/pysnmp/pysmi) integration for dynamic MIB compilation
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

To download and install PySNMP along with its dependencies:

- [PyASN1](https://github.com/pysnmp/pyasn1)
- [PyCryptodomex](https://pycryptodome.readthedocs.io) (required for SNMPv3 encryption; imported lazily, so
  SNMPv1, SNMPv2c and the SNMPv3 noAuthNoPriv/authNoPriv security levels work without it)
- [PySMI](https://github.com/pysnmp/pysmi) (required for MIB services only)

Besides the library, command-line [SNMP utilities](https://github.com/etingof/snmpclitools)
written in pure-Python could be installed via:

```bash
$ pip install snmpclitools
```

and used in the very similar manner as conventional Net-SNMP tools:

```bash
$ snmpget.py -v3 -l authPriv -u usr-md5-des -A authkey1 -X privkey1 localhost sysDescr.0
SNMPv2-MIB::sysDescr.0 = STRING: Linux localhost 5.15.0
```

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
            % (errorStatus.prettyPrint(), varBinds[int(errorIndex) - 1] if errorIndex else "?")
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
[this one](https://pysnmp.github.io/mibs/asn1/)) for that purpose.

For more example scripts please refer to the `examples/` directory in this repository.

## Documentation

Library documentation and examples can be found in the `docs/` directory in this repository.

If something does not work as expected, please
[open an issue](https://github.com/pysnmp/pysnmp/issues) at GitHub or
post your question [on Stack Overflow](https://stackoverflow.com/questions/tagged/pysnmp).

Bug reports and PRs are appreciated! ;-)

Copyright (c) 2005-2019, [Ilya Etingof deceased](https://lists.openstack.org/pipermail/openstack-discuss/2022-August/030062.html). All rights reserved.
