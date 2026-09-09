"""A pure-Python SNMP v1/v2c/v3 engine.

`pysnmp.hlapi` is the entry point for most callers. `pysnmp.entity` holds the
engine those calls are built on, `pysnmp.proto` the message processing and
security models, `pysnmp.smi` the MIB machinery, and `pysnmp.carrier` the
transports.
"""

# http://www.python.org/dev/peps/pep-0396/
__version__ = "6.0.0-rc.10"
# another variable is required to prevent semantic release from updating version in more than one place
main_version = __version__
# backward compatibility
# for pre-release versions, integer casting throws an exception, so the
# pre-release and build metadata parts must be cut off
main_version = __version__.split("-", maxsplit=1)[0].split("+", maxsplit=1)[0]
version = tuple(int(x) for x in main_version.split("."))
majorVersionId = version[0]
