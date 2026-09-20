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


class TestReadingAnUninitialisedInstance:
    """RFC 3416 section 4.2.1: noSuchInstance, not a schema object."""

    @pytest.fixture
    def uninitialised(self, smi):
        return smi["MibScalarInstance"]((1, 3, 6, 1, 2, 1, 99, 5), (0,), OctetString())

    def test_get_reports_no_such_instance(self, uninitialised):
        with pytest.raises(error.NoSuchInstanceError):
            uninitialised.readGet((uninitialised.name, None), idx=0)

    def test_test_reports_no_such_instance(self, uninitialised):
        with pytest.raises(error.NoSuchInstanceError):
            uninitialised.readTest((uninitialised.name, None), idx=0)

    def test_get_next_reports_no_such_instance(self, uninitialised):
        with pytest.raises(error.NoSuchInstanceError):
            uninitialised.readGetNext((uninitialised.name, None), idx=0, oName=())

    def test_test_next_reports_no_such_instance(self, uninitialised):
        with pytest.raises(error.NoSuchInstanceError):
            uninitialised.readTestNext((uninitialised.name, None), idx=0, oName=())

    def test_setting_a_value_makes_it_readable_again(self, smi, uninitialised):
        uninitialised.writeTest((uninitialised.name, OctetString("now set")), idx=0)
        uninitialised.writeCommit((uninitialised.name, OctetString("now set")), idx=0)

        name, value = uninitialised.readGet((uninitialised.name, None), idx=0)

        assert name == uninitialised.name
        assert value == OctetString("now set")

    def test_a_populated_instance_is_unaffected(self, smi):
        instance = smi["MibScalarInstance"](
            (1, 3, 6, 1, 2, 1, 99, 6), (0,), OctetString("value")
        )

        assert instance.readGet((instance.name, None), idx=0) == (
            instance.name,
            OctetString("value"),
        )
        assert instance.readTest((instance.name, None), idx=0) is None


class TestWalkingPastAnUninitialisedInstance:
    """A GETNEXT walk steps over the hole rather than stopping on it."""

    def test_get_next_reaches_the_following_populated_scalar(self, smi):
        base = (1, 3, 6, 1, 2, 1, 99, 10)
        tree = smi["MibTree"](base)

        first = smi["MibScalar"](base + (1,), OctetString())
        second = smi["MibScalar"](base + (2,), OctetString())
        third = smi["MibScalar"](base + (3,), OctetString())
        tree.registerSubtrees(first, second, third)

        first.registerSubtrees(
            smi["MibScalarInstance"](base + (1,), (0,), OctetString("first"))
        )
        # Declared, never populated -- the hole.
        second.registerSubtrees(
            smi["MibScalarInstance"](base + (2,), (0,), OctetString())
        )
        third.registerSubtrees(
            smi["MibScalarInstance"](base + (3,), (0,), OctetString("third"))
        )

        # (acFun, acCtx): no access-control callback, so every node is readable
        # and only the isValue gate can skip one.
        name, value = tree.readGetNext((base + (1, 0), None), idx=0)

        assert name == base + (3, 0)
        assert value == OctetString("third")
