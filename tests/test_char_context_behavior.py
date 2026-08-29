"""Characterization tests for empty-context behavior.

Verifies that ContextData and CommunityData handle default contextName
(null/b'') correctly, and that == b'' works for empty-context semantics.
"""

from pyasn1.compat.octets import null

from pysnmp.hlapi.auth import CommunityData
from pysnmp.hlapi.context import ContextData


class TestContextDataEmptyContext:
    """Test ContextData with default and explicit empty context names."""

    def test_default_context_name_is_empty_bytes(self):
        ctx = ContextData()
        assert ctx.contextName == b""
        assert ctx.contextName == null

    def test_explicit_empty_context_name(self):
        ctx = ContextData(contextName=b"")
        assert ctx.contextName == b""

    def test_explicit_none_context_name(self):
        """Passing contextName=None should set it to None, not b''."""
        ctx = ContextData(contextName=None)
        assert ctx.contextName is None

    def test_non_empty_context_name(self):
        ctx = ContextData(contextName="mycontext")
        assert ctx.contextName == "mycontext"

    def test_default_context_engine_id_is_none(self):
        ctx = ContextData()
        assert ctx.contextEngineId is None

    def test_repr_default(self):
        ctx = ContextData()
        r = repr(ctx)
        assert "contextEngineId=None" in r
        assert "contextName=" in r

    def test_repr_with_context(self):
        ctx = ContextData(contextName="mycontext")
        r = repr(ctx)
        assert "mycontext" in r


class TestCommunityDataEmptyContext:
    """Test CommunityData with default and explicit empty context names."""

    def test_default_context_name_is_empty_bytes(self):
        cd = CommunityData("public")
        assert cd.contextName == b""
        assert cd.contextName == null

    def test_explicit_empty_context_name(self):
        cd = CommunityData("public", contextName=b"")
        assert cd.contextName == b""

    def test_explicit_none_context_name(self):
        """Passing contextName=None should keep the class default (b'')."""
        cd = CommunityData("public", contextName=None)
        # The __init__ only sets contextName if it's not None
        assert cd.contextName == b""

    def test_non_empty_context_name(self):
        cd = CommunityData("public", contextName="mycontext")
        assert cd.contextName == "mycontext"

    def test_default_tag_is_empty_bytes(self):
        cd = CommunityData("public")
        assert cd.tag == b""
        assert cd.tag == null

    def test_repr_default(self):
        cd = CommunityData("public")
        r = repr(cd)
        assert "CommunityData(" in r
        assert "mpModel=" in r