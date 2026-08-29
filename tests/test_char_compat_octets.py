"""Characterization tests for pyasn1.compat.octets replacement.

These tests verify that the native Python 3 replacements are semantically
equivalent to the pyasn1.compat.octets shims, using Latin-1 (iso-8859-1)
encoding — NOT UTF-8.

Run these tests BEFORE and AFTER the pyasn1.compat replacement to verify
behavior is preserved.
"""

import pytest
from pyasn1.compat.octets import (
    str2octs,
    octs2str,
    isStringType,
    isOctetsType,
    octs2ints,
    ints2octs,
    int2oct,
    oct2int,
    null,
)


class TestStr2OctsLatin1:
    """Verify str2octs uses iso-8859-1 (Latin-1), not UTF-8."""

    def test_ascii_roundtrip(self):
        s = "hello"
        assert str2octs(s) == s.encode("iso-8859-1")
        assert octs2str(str2octs(s)) == s

    def test_empty_string(self):
        assert str2octs("") == b""
        assert octs2str(b"") == ""

    @pytest.mark.parametrize(
        "char,byte_val",
        [
            ("\x80", 0x80),
            ("\xff", 0xFF),
            ("\xe9", 0xE9),  # é in Latin-1
            ("\xfc", 0xFC),  # ü in Latin-1
            ("\xc0", 0xC0),  # À in Latin-1
        ],
    )
    def test_latin1_high_chars(self, char, byte_val):
        """Latin-1 chars (0x80-0xFF) must map to single bytes, not multi-byte UTF-8."""
        encoded = str2octs(char)
        assert len(encoded) == 1, (
            f"str2octs({char!r}) produced {len(encoded)} bytes, expected 1. "
            "This means UTF-8 is being used instead of Latin-1."
        )
        assert encoded == bytes([byte_val])

    def test_latin1_roundtrip(self):
        """Full roundtrip for all Latin-1 characters."""
        for i in range(256):
            char = chr(i)
            encoded = str2octs(char)
            decoded = octs2str(encoded)
            assert decoded == char, f"Roundtrip failed for char {i} (0x{i:02x})"
            assert encoded == char.encode("iso-8859-1")

    def test_multibyte_string(self):
        s = "café"
        assert str2octs(s) == s.encode("iso-8859-1")
        assert octs2str(str2octs(s)) == s

    def test_not_utf8(self):
        """Explicitly verify that é (0xe9) does NOT produce UTF-8 (0xc3 0xa9)."""
        encoded = str2octs("é")
        assert encoded == b"\xe9", f"Expected b'\\xe9' (Latin-1), got {encoded!r}"
        assert encoded != b"\xc3\xa9", "UTF-8 encoding detected — should be Latin-1"


class TestNullReplacement:
    """Verify null is b'' and equality (not identity) checks work."""

    def test_null_is_empty_bytes(self):
        assert null == b""

    def test_null_equality(self):
        """contextName == b'' must work for empty-context semantics."""
        contextName = null
        assert contextName == b""

    def test_explicit_empty_bytes_equality(self):
        """A separately-created b'' must equal null."""
        explicit = b""
        assert explicit == null


class TestOcts2Ints:
    """Verify octs2ints(x) behavior.

    Note: octs2ints returns bytes (not list) in this pyasn1 fork.
    The native replacement is `list(x)` or just iterating bytes directly.
    """

    def test_basic(self):
        # octs2ints returns bytes, not list
        result = octs2ints(b"\x01\x02\x03")
        assert result == b"\x01\x02\x03"
        assert list(result) == [1, 2, 3]

    def test_empty(self):
        result = octs2ints(b"")
        assert result == b""
        assert list(result) == []

    def test_high_bytes(self):
        result = octs2ints(b"\xff\x80")
        assert result == b"\xff\x80"
        assert list(result) == [255, 128]


class TestInts2Octs:
    """Verify ints2octs(xs) == bytes(xs)."""

    def test_basic(self):
        assert ints2octs([1, 2, 3]) == b"\x01\x02\x03"

    def test_empty(self):
        assert ints2octs([]) == b""

    def test_high_values(self):
        assert ints2octs([255, 0, 128]) == b"\xff\x00\x80"


class TestInt2Oct:
    """Verify int2oct(x) == bytes((x,))."""

    def test_basic(self):
        assert int2oct(65) == b"A"

    def test_zero(self):
        assert int2oct(0) == b"\x00"

    def test_max(self):
        assert int2oct(255) == b"\xff"


class TestOct2Int:
    """Verify oct2int(x) == x for bytes elements (already int in Python 3)."""

    def test_basic(self):
        assert oct2int(b"\x41"[0]) == 65

    def test_zero(self):
        assert oct2int(b"\x00"[0]) == 0

    def test_high(self):
        assert oct2int(b"\xff"[0]) == 255


class TestIsStringType:
    """Verify isStringType(x) == isinstance(x, str)."""

    def test_str(self):
        assert isStringType("hello")

    def test_bytes_not_string(self):
        assert not isStringType(b"hello")

    def test_empty_str(self):
        assert isStringType("")

    def test_int_not_string(self):
        assert not isStringType(42)


class TestIsOctetsType:
    """Verify isOctetsType(x) == isinstance(x, bytes)."""

    def test_bytes(self):
        assert isOctetsType(b"hello")

    def test_str_not_octets(self):
        assert not isOctetsType("hello")

    def test_empty_bytes(self):
        assert isOctetsType(b"")

    def test_int_not_octets(self):
        assert not isOctetsType(42)