"""Unit tests for the pysnmp.debug module."""

import logging

import pytest

from pysnmp import debug
from pysnmp.error import PySnmpError


class TestDebug:
    def test_default_flags_are_none(self):
        d = debug.Debug()
        assert d._flags == debug.flagNone

    def test_enable_flag(self):
        d = debug.Debug("io")
        assert d._flags & debug.flagIO

    def test_enable_multiple_flags(self):
        d = debug.Debug("io", "dsp")
        assert d._flags & debug.flagIO
        assert d._flags & debug.flagDsp

    def test_disable_flag_with_inverse(self):
        d = debug.Debug("io", "!io")
        assert not (d._flags & debug.flagIO)

    def test_enable_all(self):
        d = debug.Debug("all")
        assert d._flags == debug.flagAll

    def test_bad_flag_raises(self):
        with pytest.raises(PySnmpError):
            debug.Debug("bogus-flag")

    def test_flag_map_completeness(self):
        assert debug.flagMap["io"] == debug.flagIO
        assert debug.flagMap["dsp"] == debug.flagDsp
        assert debug.flagMap["msgproc"] == debug.flagMP
        assert debug.flagMap["secmod"] == debug.flagSM
        assert debug.flagMap["mibbuild"] == debug.flagBld
        assert debug.flagMap["mibview"] == debug.flagMIB
        assert debug.flagMap["mibinstrum"] == debug.flagIns
        assert debug.flagMap["acl"] == debug.flagACL
        assert debug.flagMap["proxy"] == debug.flagPrx
        assert debug.flagMap["app"] == debug.flagApp
        assert debug.flagMap["all"] == debug.flagAll

    def test_printer_callable(self):
        printer = debug.Printer()
        # Should not raise
        printer("test message")

    def test_printer_str(self):
        printer = debug.Printer()
        assert "logging" in str(printer)

    def test_debug_str(self):
        d = debug.Debug("io")
        assert "flags" in str(d)

    def test_debug_with_logger_name(self):
        d = debug.Debug(loggerName="test-logger")
        assert d._flags == debug.flagNone

    def test_debug_call_logs_message(self):
        d = debug.Debug("io")
        # __call__ should not raise
        d("a test debug message")

    def test_null_handler(self):
        handler = debug.NullHandler()
        record = logging.LogRecord(
            "test", logging.DEBUG, __file__, 1, "msg", None, None
        )
        # Should not raise
        handler.emit(record)


class TestDebugOff:
    """The switch installed while debugging is off.

    It stands in for a Debug instance so the ``logger & flag and logger(msg)``
    idiom has one callable type either way. See pysnmp/pysnmp#178.
    """

    def test_module_logger_starts_off(self):
        assert isinstance(debug.logger, debug.DebugOff)

    def test_is_falsy(self):
        assert not debug.DEBUG_OFF

    def test_and_with_any_flag_is_false(self):
        for flag in debug.flagMap.values():
            assert not (debug.DEBUG_OFF & flag)
            assert not (flag & debug.DEBUG_OFF)

    def test_call_is_silent(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="pysnmp"):
            assert debug.DEBUG_OFF("a message nobody wants") is None
        assert caplog.records == []

    def test_str(self):
        assert str(debug.DEBUG_OFF) == "<debugging off>"

    def test_set_logger_installs_and_restores(self):
        try:
            d = debug.Debug("io")
            debug.setLogger(d)
            assert debug.logger is d
            assert debug.logger & debug.flagIO
        finally:
            debug.setLogger(None)
        assert debug.logger is debug.DEBUG_OFF

    def test_set_logger_zero_turns_debugging_off(self):
        # 0 is how the flag was historically switched off, and still is.
        debug.setLogger(debug.Debug("io"))
        try:
            debug.setLogger(0)
            assert debug.logger is debug.DEBUG_OFF
            assert not (debug.logger & debug.flagIO)
        finally:
            debug.setLogger(None)
