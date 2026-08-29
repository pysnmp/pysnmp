"""Characterization tests for comparison behavior.

Tests ErrorIndication, TimerCallable, and ObjectIdentity comparison
operators. Specifically tests ObjectIdentity.__ge__ which currently
delegates to > instead of >= (existing bug that total_ordering will fix).
"""

import pytest
from pysnmp.proto.errind import ErrorIndication, SerializationError
from pysnmp.carrier.base import TimerCallable
from pysnmp.smi.rfc1902 import ObjectIdentity
from pysnmp.smi import builder, view


class TestErrorIndicationComparison:
    """Test ErrorIndication comparison operators.

    Note: ErrorIndication.__value is always the class name (lowercased first char),
    NOT the descr parameter. The descr only changes __descr (used by __str__).
    So two SerializationError() instances always have the same __value.
    Comparisons compare __value against the other object directly.
    """

    def test_eq(self):
        e1 = SerializationError()
        e2 = SerializationError()
        assert e1 == e2

    def test_eq_with_string(self):
        e = SerializationError()
        assert e == "serializationError"

    def test_ne_with_different_string(self):
        e1 = SerializationError()
        assert e1 != "differentError"

    def test_ne_same_class_same_value(self):
        """Two instances of the same class have the same __value."""
        e1 = SerializationError()
        e2 = SerializationError("custom")
        # __value is always "serializationError" regardless of descr
        assert e1 == e2

    def test_lt_with_string(self):
        e1 = SerializationError()  # __value = "serializationError"
        assert e1 < "zzz"  # "serializationError" < "zzz"

    def test_le_equal_with_string(self):
        e1 = SerializationError()
        assert e1 <= "serializationError"

    def test_le_less_with_string(self):
        e1 = SerializationError()
        assert e1 <= "zzz"

    def test_gt_with_string(self):
        e1 = SerializationError()
        assert e1 > "aaa"  # "serializationError" > "aaa"

    def test_ge_equal_with_string(self):
        e1 = SerializationError()
        assert e1 >= "serializationError"

    def test_ge_correct_semantics(self):
        """__ge__ should use >=, not >. With equal values, >= is True but > is False."""
        e1 = SerializationError()
        assert e1 >= "serializationError", (
            "ErrorIndication.__ge__ should return True for equal values. "
            "If this fails, __ge__ may be delegating to > instead of >=."
        )


class TestTimerCallableComparison:
    """Test TimerCallable comparison operators."""

    def test_eq_with_callable(self):
        def cb(time):
            pass

        tc = TimerCallable(cb, 5)
        assert tc == cb

    def test_ne_with_different_callable(self):
        def cb1(time):
            pass

        def cb2(time):
            pass

        tc = TimerCallable(cb1, 5)
        assert tc != cb2

    def test_lt_with_int(self):
        tc = TimerCallable(10, 5)
        assert tc < 20

    def test_le_with_int(self):
        tc = TimerCallable(10, 5)
        assert tc <= 10

    def test_gt_with_int(self):
        tc = TimerCallable(20, 5)
        assert tc > 10

    def test_ge_with_int(self):
        tc = TimerCallable(10, 5)
        assert tc >= 10

    def test_ge_correct_semantics(self):
        """__ge__ should use >=, not >. With equal values, >= is True but > is False."""
        tc = TimerCallable(10, 5)
        assert tc >= 10, (
            "TimerCallable.__ge__ should return True for equal values. "
            "If this fails, __ge__ may be delegating to > instead of >=."
        )


class TestObjectIdentityComparison:
    """Test ObjectIdentity comparison operators.

    Note: ObjectIdentity must be resolved with a MIB controller before
    comparisons work. Unresolved OIDs raise SmiError.
    """

    @pytest.fixture
    def resolved_oid(self):
        oid = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        mibBuilder = builder.MibBuilder()
        mibView = view.MibViewController(mibBuilder)
        oid.resolveWithMib(mibView)
        return oid

    @pytest.fixture
    def resolved_oid2(self):
        oid = ObjectIdentity("1.3.6.1.2.1.1.1.1")
        mibBuilder = builder.MibBuilder()
        mibView = view.MibViewController(mibBuilder)
        oid.resolveWithMib(mibView)
        return oid

    def test_eq_with_tuple(self, resolved_oid):
        assert resolved_oid == (1, 3, 6, 1, 2, 1, 1, 1, 0)

    def test_ne_with_different_tuple(self, resolved_oid, resolved_oid2):
        assert resolved_oid != resolved_oid2

    def test_lt(self, resolved_oid, resolved_oid2):
        assert resolved_oid < resolved_oid2

    @pytest.mark.xfail(
        reason="BUG: ObjectIdentity.__le__ delegates to < instead of <=. "
        "For equal OIDs, < returns False but <= should return True. "
        "Fixed by total_ordering in Phase 5."
    )
    def test_le_equal(self, resolved_oid):
        oid2 = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        mibBuilder = builder.MibBuilder()
        mibView = view.MibViewController(mibBuilder)
        oid2.resolveWithMib(mibView)
        assert resolved_oid <= oid2

    def test_le_less(self, resolved_oid, resolved_oid2):
        assert resolved_oid <= resolved_oid2

    def test_gt(self, resolved_oid, resolved_oid2):
        assert resolved_oid2 > resolved_oid

    def test_ge_greater(self, resolved_oid, resolved_oid2):
        assert resolved_oid2 >= resolved_oid

    @pytest.mark.xfail(
        reason="BUG: ObjectIdentity.__ge__ delegates to > instead of >=. "
        "For equal OIDs, > returns False but >= should return True. "
        "Fixed by total_ordering in Phase 5."
    )
    def test_ge_equal(self, resolved_oid):
        """__ge__ should use >=, not >. With equal OIDs, >= is True but > is False.

        This is the KNOWN BUG: ObjectIdentity.__ge__ currently delegates to
        > instead of >=. This test documents the bug and will pass AFTER
        total_ordering is applied (which synthesizes correct __ge__).
        """
        oid2 = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        mibBuilder = builder.MibBuilder()
        mibView = view.MibViewController(mibBuilder)
        oid2.resolveWithMib(mibView)
        result = resolved_oid >= oid2
        assert result, (
            "ObjectIdentity.__ge__ returns False for equal OIDs. "
            "This is the known bug — __ge__ delegates to > instead of >=. "
            "total_ordering will fix this."
        )