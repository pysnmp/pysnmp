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
        d = debug.Debug('io')
        assert d._flags & debug.flagIO

    def test_enable_multiple_flags(self):
        d = debug.Debug('io', 'dsp')
        assert d._flags & debug.flagIO
        assert d._flags & debug.flagDsp

    def test_disable_flag_with_inverse(self):
        d = debug.Debug('io', '!io')
        assert not (d._flags & debug.flagIO)

    def test_enable_all(self):
        d = debug.Debug('all')
        assert d._flags == debug.flagAll

    def test_bad_flag_raises(self):
        with pytest.raises(PySnmpError):
            debug.Debug('bogus-flag')

    def test_flag_map_completeness(self):
        assert debug.flagMap['io'] == debug.flagIO
        assert debug.flagMap['dsp'] == debug.flagDsp
        assert debug.flagMap['msgproc'] == debug.flagMP
        assert debug.flagMap['secmod'] == debug.flagSM
        assert debug.flagMap['mibbuild'] == debug.flagBld
        assert debug.flagMap['mibview'] == debug.flagMIB
        assert debug.flagMap['mibinstrum'] == debug.flagIns
        assert debug.flagMap['acl'] == debug.flagACL
        assert debug.flagMap['proxy'] == debug.flagPrx
        assert debug.flagMap['app'] == debug.flagApp
        assert debug.flagMap['all'] == debug.flagAll

    def test_printer_callable(self):
        printer = debug.Printer()
        # Should not raise
        printer('test message')

    def test_printer_str(self):
        printer = debug.Printer()
        assert 'logging' in str(printer)

    def test_debug_str(self):
        d = debug.Debug('io')
        assert 'flags' in str(d)

    def test_debug_with_logger_name(self):
        d = debug.Debug(loggerName='test-logger')
        assert d._flags == debug.flagNone

    def test_debug_call_logs_message(self):
        d = debug.Debug('io')
        # __call__ should not raise
        d('a test debug message')

    def test_null_handler(self):
        handler = debug.NullHandler()
        record = logging.LogRecord(
            'test', logging.DEBUG, __file__, 1, 'msg', None, None
        )
        # Should not raise
        handler.emit(record)