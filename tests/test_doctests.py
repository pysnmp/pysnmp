import doctest
import importlib

import pytest


DOCTESTED_MODULES = [
    "pysnmp.smi.rfc1902",
    "pysnmp.hlapi.asyncio.transport",
    "pysnmp.hlapi.asyncio.cmdgen",
    "pysnmp.hlapi.auth",
    "pysnmp.smi.view",
    "pysnmp.hlapi.context",
    "pysnmp.hlapi.asyncio.ntforg",
    "pysnmp.entity.engine",
]


@pytest.mark.parametrize("module_name", DOCTESTED_MODULES)
def test_doctests(module_name):
    module = importlib.import_module(module_name)
    result = doctest.testmod(module, verbose=False)

    assert result.failed == 0, f"{module_name} has {result.failed} failing doctest(s)"
