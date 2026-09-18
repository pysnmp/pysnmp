"""Agent-side value handling on ``MibScalarInstance``.

Two things a managed object has to get right before anything above it can:
what "no value supplied" means on a write, and what a read of an instance that
was declared but never populated answers with.
"""

import pytest

from pysnmp.proto.rfc1902 import Integer32, OctetString
from pysnmp.smi import error
from pysnmp.smi.builder import MibBuilder


@pytest.fixture(scope="module")
def smi():
    """``SNMPv2-SMI`` and ``SNMPv2-TC`` classes, built once."""
    built = MibBuilder()
    (MibScalarInstance, MibScalar, MibTree) = built.importSymbols(
        "SNMPv2-SMI", "MibScalarInstance", "MibScalar", "MibTree"
    )
    (TestAndIncr,) = built.importSymbols("SNMPv2-TC", "TestAndIncr")

    return {
        "MibScalarInstance": MibScalarInstance,
        "MibScalar": MibScalar,
        "MibTree": MibTree,
        "TestAndIncr": TestAndIncr,
    }


class TestSetValueWithoutAValue:
    """``setValue(None)`` -- "take the column default"."""

    def test_a_test_and_incr_column_yields_its_default(self, smi):
        # etingof/pysnmp#316. Row creation passes None for every column the
        # manager did not name. That used to be turned into pyasn1's noValue and
        # handed to the syntax's own setValue(); TestAndIncr's compares the
        # incoming value, and pyasn1 refuses __ne__ against a schema object, so
        # the write failed with WrongValueError. One TestAndIncr column anywhere
        # in a table made every row in it un-creatable.
        instance = smi["MibScalarInstance"](
            (1, 3, 6, 1, 2, 1, 99, 1), (0,), smi["TestAndIncr"](0)
        )

        default = instance.setValue(None, instance.name, 0)

        assert default.isValue
        assert int(default) == 0

    @pytest.mark.parametrize(
        "syntax",
        [OctetString("preset"), Integer32(42)],
        ids=["OctetString", "Integer32"],
    )
    def test_an_ordinary_syntax_yields_its_default(self, smi, syntax):
        instance = smi["MibScalarInstance"]((1, 3, 6, 1, 2, 1, 99, 2), (0,), syntax)

        assert instance.setValue(None, instance.name, 0) == syntax

    def test_a_supplied_value_is_still_applied(self, smi):
        instance = smi["MibScalarInstance"](
            (1, 3, 6, 1, 2, 1, 99, 3), (0,), OctetString("old")
        )

        assert instance.setValue(OctetString("new"), instance.name, 0) == OctetString(
            "new"
        )

    def test_a_rejected_value_still_raises(self, smi):
        # The guard above must not swallow a genuinely bad write.
        instance = smi["MibScalarInstance"](
            (1, 3, 6, 1, 2, 1, 99, 4), (0,), Integer32(0)
        )

        with pytest.raises(error.WrongValueError):
            instance.setValue(OctetString("not an integer"), instance.name, 0)
