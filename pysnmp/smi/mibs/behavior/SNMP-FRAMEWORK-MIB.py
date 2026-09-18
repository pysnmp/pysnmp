# RFC 3411 section 5 and the SnmpEngineID DESCRIPTION clause give an algorithm
# for an engine to derive its own identifier when an operator configures none:
# pysnmp's enterprise number, then whatever local properties distinguish this
# engine from another on the same host. An initial value an implementation
# computes at import time is not something the module states, so it is written
# here.

import os as _os
import platform as _platform

# 1.3.6.1.4.1.20408 -- pysnmp's IANA enterprise number, high bit set as RFC 3411
# section 5 requires of the first four octets. PYSNMP-MIB states the arc.
_defaultValue = [128, 0, 79, 184, 5]

# Base the engine ID on the local system name.
#
# platform.node() rather than os.uname()[1]: os.uname() does not exist on
# Windows, so the try/except this used to sit in swallowed the AttributeError
# there and the hostname contributed nothing at all. That left a Windows engine
# with the 5-octet prefix, two octets of PID and two of an object address --
# four varying octets, part of which is an address that is far from uniformly
# random. RFC 3411 section 5 wants an identifier that distinguishes this engine
# from every other, and two Windows hosts colliding on four octets is not
# remote; a collision breaks USM time synchronisation and key localisation
# between them.
#
# platform.node() answers on every platform, and returns "" rather than raising
# where it cannot tell. It can hold non-ASCII, so the octets are taken by
# encoding rather than by ord() -- which is what the old try/except was really
# hiding. The 16-octet bound is on the encoded form, since that is what goes
# into the identifier.
_defaultValue += list(_platform.node().encode("utf-8", "replace")[:16])

try:
    # ...and on the process, so two engines on one host still differ.
    _defaultValue += [_os.getpid() >> 8 & 0xFF, _os.getpid() & 0xFF]
except Exception:  # noqa: BLE001, S110 - best-effort seed, as above
    pass

# ...and on an address, so two engines in one process still differ.
_defaultValue += [id(_defaultValue) >> 8 & 0xFF, id(_defaultValue) & 0xFF]

SnmpEngineID.defaultValue = OctetString(_defaultValue).asOctets()

# A fragment runs after the module built its objects, so the syntax the scalar
# already holds was constructed while defaultValue was unset and is valueless.
# Rebuild it, now that the class states a default. pysnmp reads this one as a
# value rather than as a schema -- MibScalarInstance takes snmpEngineID.syntax
# in pysnmp/smi/mibs/instances/__SNMP-FRAMEWORK-MIB.py, and config.py answers
# with it for contextEngineId. See pysnmp/pysmi#236.
snmpEngineID.syntax = SnmpEngineID()
