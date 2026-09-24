"""Regression tests for PySnmpError cause attribution.

PySnmpError used to snapshot sys.exc_info() in __init__, which reports the
exception being handled anywhere up the stack at construction time — not the
one this error was raised from. Constructing an error inside an unrelated
except block therefore glued a stranger's exception onto the message.

Cause now derives from __cause__/__context__, which Python sets at raise time.
"""

import pytest

from pysnmp.error import PySnmpError


class TestUnchainedError:
    """An error with no chained exception reports none."""

    def test_str_is_just_the_message(self):
        assert str(PySnmpError("bad config")) == "bad config"

    def test_cause_is_empty_triple(self):
        assert PySnmpError("bad config").cause == (None, None, None)

    def test_no_args(self):
        assert str(PySnmpError()) == ""

    def test_constructed_inside_unrelated_except_block(self):
        """Construction is not a raise; a handled exception is not our cause."""
        try:
            raise ValueError("unrelated parsing failure")
        except ValueError:
            exc = PySnmpError("bad config")
        assert str(exc) == "bad config"
        assert exc.cause == (None, None, None)

    def test_caller_further_up_is_handling_an_exception(self):
        try:
            raise OSError("socket closed")
        except OSError:
            exc = PySnmpError("bad config")
        assert str(exc) == "bad config"


class TestChainedError:
    """An error raised while handling another reports that one."""

    def test_implicit_context(self):
        with pytest.raises(PySnmpError) as info:
            try:
                raise ValueError("bad BER")
            except ValueError:
                raise PySnmpError("decode failed")
        assert str(info.value) == "decode failed, caused by ValueError: bad BER"
        assert info.value.cause[0] is ValueError

    def test_explicit_from(self):
        with pytest.raises(PySnmpError) as info:
            try:
                raise KeyError("nope")
            except KeyError as exc:
                raise PySnmpError("lookup failed") from exc
        assert info.value.cause[0] is KeyError

    def test_explicit_from_outranks_context(self):
        chosen = TypeError("the real cause")
        with pytest.raises(PySnmpError) as info:
            try:
                raise ValueError("incidental")
            except ValueError:
                raise PySnmpError("failed") from chosen
        assert info.value.cause[1] is chosen

    def test_cause_triple_carries_traceback(self):
        with pytest.raises(PySnmpError) as info:
            try:
                raise ValueError("bad BER")
            except ValueError:
                raise PySnmpError("decode failed")
        kind, value, traceback = info.value.cause
        assert kind is ValueError
        assert isinstance(value, ValueError)
        assert traceback is value.__traceback__

    def test_message_omitted_when_error_has_no_args(self):
        with pytest.raises(PySnmpError) as info:
            try:
                raise ValueError("bad BER")
            except ValueError:
                raise PySnmpError
        assert str(info.value) == "caused by ValueError: bad BER"


class TestSubclasses:
    """Cause handling reaches the subclasses that inherit it."""

    def test_smi_error(self):
        from pysnmp.smi.error import SmiError

        with pytest.raises(SmiError) as info:
            try:
                raise ValueError("no such module")
            except ValueError:
                raise SmiError("MIB load failed")
        assert info.value.cause[0] is ValueError

    def test_protocol_error(self):
        from pysnmp.proto.error import ProtocolError

        with pytest.raises(ProtocolError) as info:
            try:
                raise ValueError("truncated")
            except ValueError:
                raise ProtocolError("bad PDU")
        assert "caused by ValueError: truncated" in str(info.value)
