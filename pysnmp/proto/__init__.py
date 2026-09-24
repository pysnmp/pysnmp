# This file is necessary to make this directory a package.
"""SNMP itself: the message formats, and the models that process and secure them.

The `rfc*` modules are the wire types. `mpmod` prepares and parses messages
per version, `secmod` authenticates and encrypts them, `acmod` decides who may
see what, and `api` is a version-independent way to build and read a PDU.
"""
