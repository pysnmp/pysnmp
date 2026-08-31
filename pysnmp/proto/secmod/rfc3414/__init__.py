#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

# Lazy import to break circular dependency: service.py imports eso.priv
# modules which import rfc3414.localkey/auth via this __init__.py
import importlib as _importlib


def __getattr__(name):
    if name == "SnmpUSMSecurityModel":
        _service = _importlib.import_module("pysnmp.proto.secmod.rfc3414.service")
        return _service.SnmpUSMSecurityModel
    if name == "service":
        return _importlib.import_module("pysnmp.proto.secmod.rfc3414.service")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
