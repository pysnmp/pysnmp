"""Characterization tests for repr format strings.

Locks in the exact repr format for ContextData, CommunityData,
UsmUserData, and nextid.Integer before any @dataclass or f-string changes.
"""

import re

from pysnmp.hlapi.auth import CommunityData, UsmUserData
from pysnmp.hlapi.context import ContextData
from pysnmp.nextid import Integer


class TestContextDataRepr:
    def test_repr_default(self):
        ctx = ContextData()
        r = repr(ctx)
        assert r.startswith("ContextData(")
        assert "contextEngineId=None" in r
        assert "contextName=" in r

    def test_repr_with_context_name(self):
        ctx = ContextData(contextName="mycontext")
        r = repr(ctx)
        assert "mycontext" in r

    def test_repr_format_pattern(self):
        """Verify the repr follows the expected pattern."""
        ctx = ContextData()
        r = repr(ctx)
        # Pattern: ContextData(contextEngineId=<value>, contextName=<value>)
        assert re.match(
            r"ContextData\(contextEngineId=.*, contextName=.*\)", r
        ), f"Unexpected repr format: {r}"


class TestCommunityDataRepr:
    def test_repr_basic(self):
        cd = CommunityData("public")
        r = repr(cd)
        assert r.startswith("CommunityData(")
        assert "communityIndex=" in r
        assert "communityName=<COMMUNITY>" in r
        assert "mpModel=" in r
        assert "contextEngineId=" in r
        assert "contextName=" in r
        assert "tag=" in r
        assert "securityName=" in r

    def test_repr_with_explicit_index(self):
        cd = CommunityData("public", "public")
        r = repr(cd)
        assert "communityIndex='public'" in r

    def test_repr_format_pattern(self):
        cd = CommunityData("public")
        r = repr(cd)
        assert re.match(
            r"CommunityData\(communityIndex=.*, communityName=<COMMUNITY>, "
            r"mpModel=.*, contextEngineId=.*, contextName=.*, tag=.*, "
            r"securityName=.*\)",
            r,
        ), f"Unexpected repr format: {r}"


class TestUsmUserDataRepr:
    def test_repr_basic(self):
        user = UsmUserData("testuser", authKey="mykey", privKey="mypriv")
        r = repr(user)
        assert r.startswith("UsmUserData(")
        assert "userName='testuser'" in r
        assert "authKey=<AUTHKEY>" in r
        assert "privKey=<PRIVKEY>" in r
        assert "authProtocol=" in r
        assert "privProtocol=" in r
        assert "securityEngineId=" in r
        assert "securityName=" in r
        assert "authKeyType=" in r
        assert "privKeyType=" in r

    def test_repr_default_security_engine_id(self):
        user = UsmUserData("testuser")
        r = repr(user)
        assert "<DEFAULT>" in r

    def test_repr_with_security_engine_id(self):
        user = UsmUserData("testuser", securityEngineId="0x010203")
        r = repr(user)
        assert "0x010203" in r

    def test_repr_format_pattern(self):
        user = UsmUserData("testuser")
        r = repr(user)
        assert re.match(
            r"UsmUserData\(userName=.*, authKey=<AUTHKEY>, privKey=<PRIVKEY>, "
            r"authProtocol=.*, privProtocol=.*, securityEngineId=.*, "
            r"securityName=.*, authKeyType=.*, privKeyType=.*\)",
            r,
        ), f"Unexpected repr format: {r}"


class TestIntegerRepr:
    def test_repr_format(self):
        i = Integer(1000, 256)
        r = repr(i)
        assert re.match(r"Integer\(\d+, \d+\)", r), f"Unexpected repr format: {r}"

    def test_repr_contains_class_name(self):
        i = Integer(1000, 256)
        r = repr(i)
        assert "Integer(" in r

    def test_repr_contains_max_and_increment(self):
        i = Integer(1000, 256)
        r = repr(i)
        assert "1000" in r
        assert "256" in r