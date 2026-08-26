"""Unit tests for pysnmp.error, pysnmp.nextid, and pysnmp.cache modules."""

import pytest

from pysnmp.error import PySnmpError
from pysnmp.nextid import Integer as NextIdInteger
from pysnmp.cache import Cache


class TestPySnmpError:
    def test_error_with_message(self):
        err = PySnmpError('something went wrong')
        assert 'something went wrong' in str(err)

    def test_error_no_args(self):
        err = PySnmpError()
        # Should not raise
        str(err)

    def test_error_is_exception(self):
        with pytest.raises(PySnmpError):
            raise PySnmpError('test')


class TestNextIdInteger:
    def test_returns_int(self):
        gen = NextIdInteger(0xffffff)
        val = gen()
        assert isinstance(val, int)

    def test_returns_in_range(self):
        gen = NextIdInteger(0xffffff)
        for _ in range(10):
            val = gen()
            assert 0 <= val <= 0xffffff

    def test_repr(self):
        gen = NextIdInteger(1000, 100)
        assert 'Integer' in repr(gen)

    def test_increment_not_capped(self):
        gen = NextIdInteger(1000, 100)
        assert gen._Integer__increment == 100

    def test_consecutive_calls_differ(self):
        gen = NextIdInteger(0xffffff)
        vals = [gen() for _ in range(20)]
        # Most consecutive values should differ
        unique = set(vals)
        assert len(unique) > 10


class TestCache:
    def test_set_and_get(self):
        c = Cache(maxSize=10)
        c['a'] = 1
        assert c['a'] == 1
        assert 'a' in c

    def test_len(self):
        c = Cache(maxSize=10)
        c['a'] = 1
        c['b'] = 2
        assert len(c) == 2

    def test_delete(self):
        c = Cache(maxSize=10)
        c['a'] = 1
        del c['a']
        assert 'a' not in c
        assert len(c) == 0

    def test_eviction_on_overflow(self):
        c = Cache(maxSize=5)
        for i in range(6):
            c[i] = i
        # After inserting 6 items into a size-5 cache, some eviction occurs
        assert len(c) <= 5

    def test_usage_tracking(self):
        c = Cache(maxSize=10)
        c['a'] = 1
        c['b'] = 2
        # Access 'a' more so it survives eviction
        for _ in range(5):
            _ = c['a']
        _ = c['b']
        # Fill cache to trigger eviction
        for i in range(10):
            c[i] = i
        # 'a' was used more, should still be present
        assert 'a' in c