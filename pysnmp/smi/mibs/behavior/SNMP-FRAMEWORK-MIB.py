# RFC 3411 section 5 and the SnmpEngineID DESCRIPTION clause give an algorithm
# for an engine to derive its own identifier when an operator configures none:
# pysnmp's enterprise number, then whatever local properties distinguish this
# engine from another on the same host. An initial value an implementation
# computes at import time is not something the module states, so it is written
# here.

import os as _os

# 1.3.6.1.4.1.20408 -- pysnmp's IANA enterprise number, high bit set as RFC 3411
# section 5 requires of the first four octets. PYSNMP-MIB states the arc.
_defaultValue = [128, 0, 79, 184, 5]

try:
    # Base the engine ID on the local system name.
    _defaultValue += [ord(x) for x in _os.uname()[1][:16]]
except Exception:  # noqa: BLE001, S110 - a platform without uname() contributes nothing
    pass

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
