"""Tests for the native bytes and str operations used by the package.

Text-to-bytes conversions use Latin-1 (iso-8859-1), not UTF-8, to preserve
the SNMP octet semantics formerly supplied by a compatibility helper.
"""

import pytest


class TestLatin1Encoding:
    """Verify Latin-1 encoding is used for text-to-octet conversion."""

    def test_ascii_roundtrip(self):
        s = "hello"
        assert s.encode("iso-8859-1") == b"hello"
        assert b"hello".decode("iso-8859-1") == s

    def test_empty_string(self):
        assert "".encode("iso-8859-1") == b""
        assert b"".decode("iso-8859-1") == ""

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
        encoded = char.encode("iso-8859-1")
        assert len(encoded) == 1, (
            f"Encoding {char!r} produced {len(encoded)} bytes, expected 1. "
            "This means UTF-8 is being used instead of Latin-1."
        )
        assert encoded == bytes([byte_val])

    def test_latin1_roundtrip(self):
        """Full roundtrip for all Latin-1 characters."""
        for i in range(256):
            char = chr(i)
            encoded = char.encode("iso-8859-1")
            decoded = encoded.decode("iso-8859-1")
            assert decoded == char, f"Roundtrip failed for char {i} (0x{i:02x})"
            assert encoded == char.encode("iso-8859-1")

    def test_multibyte_string(self):
        s = "café"
        encoded = s.encode("iso-8859-1")
        assert encoded == b"caf\xe9"
        assert encoded.decode("iso-8859-1") == s

    def test_not_utf8(self):
        """Explicitly verify that é (0xe9) does NOT produce UTF-8 (0xc3 0xa9)."""
        encoded = "é".encode("iso-8859-1")
        assert encoded == b"\xe9", f"Expected b'\\xe9' (Latin-1), got {encoded!r}"
        assert encoded != b"\xc3\xa9", "UTF-8 encoding detected — should be Latin-1"


class TestEmptyBytes:
    """Verify empty-byte values use equality checks."""

    def test_null_is_empty_bytes(self):
        assert b"" == b""

    def test_null_equality(self):
        """contextName == b'' must work for empty-context semantics."""
        contextName = b""
        assert contextName == b""

    def test_explicit_empty_bytes_equality(self):
        """Separately-created empty byte strings must compare equal."""
        explicit = b""
        assert explicit == b""


class TestBytesIteration:
    """Verify bytes can be iterated directly as integer octets."""

    def test_basic(self):
        result = b"\x01\x02\x03"
        assert result == b"\x01\x02\x03"
        assert list(result) == [1, 2, 3]

    def test_empty(self):
        result = b""
        assert result == b""
        assert list(result) == []

    def test_high_bytes(self):
        result = b"\xff\x80"
        assert result == b"\xff\x80"
        assert list(result) == [255, 128]


class TestBytesFromIntegers:
    """Verify bytes(xs) creates octets from integer values."""

    def test_basic(self):
        assert bytes([1, 2, 3]) == b"\x01\x02\x03"

    def test_empty(self):
        assert bytes([]) == b""

    def test_high_values(self):
        assert bytes([255, 0, 128]) == b"\xff\x00\x80"


class TestSingleIntegerByte:
    """Verify bytes((x,)) creates one octet."""

    def test_basic(self):
        assert bytes((65,)) == b"A"

    def test_zero(self):
        assert bytes((0,)) == b"\x00"

    def test_max(self):
        assert bytes((255,)) == b"\xff"


class TestBytesElements:
    """Verify bytes elements are integers in Python 3."""

    def test_basic(self):
        assert b"\x41"[0] == 65

    def test_zero(self):
        assert b"\x00"[0] == 0

    def test_high(self):
        assert b"\xff"[0] == 255


class TestStringType:
    """Verify isinstance(x, str) identifies text."""

    def test_str(self):
        assert isinstance("hello", str)

    def test_bytes_not_string(self):
        assert not isinstance(b"hello", str)

    def test_empty_str(self):
        assert isinstance("", str)

    def test_int_not_string(self):
        assert not isinstance(42, str)


class TestOctetsType:
    """Verify isinstance(x, bytes) identifies octets."""

    def test_bytes(self):
        assert isinstance(b"hello", bytes)

    def test_str_not_octets(self):
        assert not isinstance("hello", bytes)

    def test_empty_bytes(self):
        assert isinstance(b"", bytes)

    def test_int_not_octets(self):
        assert not isinstance(42, bytes)
