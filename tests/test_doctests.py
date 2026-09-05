"""Runs the doctests in modules whose examples are known to be correct.

Nothing ran these, so they rotted: 31 of the 71 examples in
``pysnmp.proto.rfc1902`` were failing when this file was added, most of them
against a pyasn1 repr that changed years ago. See #161.

Modules are added to ``DOCTESTED_MODULES`` as their examples are corrected.
The remaining modules carrying stale examples are tracked in #168.
"""

import doctest
import importlib

import pytest

DOCTESTED_MODULES = [
    "pysnmp.proto.rfc1902",
]


@pytest.mark.parametrize("module_name", DOCTESTED_MODULES)
def test_module_doctests(module_name):
    module = importlib.import_module(module_name)
    results = doctest.testmod(module, verbose=False, report=True)
    assert results.attempted, f"{module_name} has no doctests to run"
    assert results.failed == 0, (
        f"{results.failed} of {results.attempted} doctests failed in {module_name}"
    )
