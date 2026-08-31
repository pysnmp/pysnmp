"""Characterization tests for falsy clone overrides.

Tests that CommunityData.clone() and UsmUserData.clone() preserve
explicit falsy values (0, '', b'') rather than silently replacing them
with None or fallback values via the old-style ternary pattern
`x is None and self.x or x`.

These tests expose the bug where `x is None and self.x or x` evaluates
to `x` (not `self.x`) when `self.x` is falsy, even if `x is None`.
"""

import pytest

from pysnmp.hlapi.auth import CommunityData, UsmUserData


class TestCommunityDataCloneFalsy:
    """Test that CommunityData.clone() preserves falsy values."""

    @pytest.mark.xfail(
        reason="BUG: old-style ternary `mpModel is None and self.mpModel or mpModel` "
        "replaces mpModel=0 (falsy) with class default. Fixed in Phase 4."
    )
    def test_clone_preserves_mpModel_zero(self):
        """mpModel=0 (SNMPv1) is falsy — must not be replaced by fallback."""
        cd = CommunityData("public", mpModel=0)
        cloned = cd.clone()
        assert cloned.mpModel == 0, (
            f"Expected mpModel=0, got {cloned.mpModel}. "
            "Old-style ternary may have replaced it with the class default."
        )

    def test_clone_with_explicit_mpModel_zero(self):
        cd = CommunityData("public", mpModel=1)
        cloned = cd.clone(mpModel=0)
        assert cloned.mpModel == 0

    @pytest.mark.xfail(
        reason="BUG: old-style ternary `contextName is None and self.contextName or contextName` "
        "replaces contextName='' (falsy) with class default (b''). Fixed in Phase 4."
    )
    def test_clone_preserves_empty_context_name(self):
        """contextName='' is falsy — must not be replaced by fallback."""
        cd = CommunityData("public", contextName="")
        cloned = cd.clone()
        assert cloned.contextName == "", (
            f"Expected contextName='', got {cloned.contextName!r}. "
            "Old-style ternary may have replaced it with the class default."
        )

    def test_clone_with_explicit_empty_context_name(self):
        cd = CommunityData("public", contextName="mycontext")
        cloned = cd.clone(contextName="")
        assert cloned.contextName == ""

    @pytest.mark.xfail(
        reason="BUG: old-style ternary `tag is None and self.tag or tag` "
        "replaces tag='' (falsy) with class default (b''). Fixed in Phase 4."
    )
    def test_clone_preserves_empty_tag(self):
        """tag='' is falsy — must not be replaced by fallback."""
        cd = CommunityData("public", tag="")
        cloned = cd.clone()
        assert cloned.tag == ""

    def test_clone_with_explicit_empty_tag(self):
        cd = CommunityData("public", tag="mytag")
        cloned = cd.clone(tag="")
        assert cloned.tag == ""

    @pytest.mark.xfail(
        reason="BUG: old-style ternary `securityName is None and self.securityName or securityName` "
        "may replace securityName='' (falsy) with fallback. Fixed in Phase 4."
    )
    def test_clone_preserves_empty_security_name(self):
        """securityName='' is falsy — must not be replaced by fallback."""
        cd = CommunityData("public", securityName="")
        cloned = cd.clone()
        assert cloned.securityName == ""

    @pytest.mark.xfail(
        reason="BUG: old-style ternary may replace securityName='' with fallback. Fixed in Phase 4."
    )
    def test_clone_with_explicit_empty_security_name(self):
        cd = CommunityData("public", securityName="mysec")
        cloned = cd.clone(securityName="")
        assert cloned.securityName == ""

    def test_clone_preserves_community_name(self):
        cd = CommunityData("public")
        cloned = cd.clone()
        assert cloned.communityName == "public"

    def test_clone_with_new_community_name(self):
        cd = CommunityData("public")
        cloned = cd.clone("private")
        assert cloned.communityName == "private"


class TestUsmUserDataCloneFalsy:
    """Test that UsmUserData.clone() preserves falsy values."""

    def test_clone_preserves_empty_auth_key(self):
        """authKey=b'' is falsy — but in current code, None authKey means
        'no auth', so we test that clone() without args preserves the
        original authKey."""
        user = UsmUserData("testuser", authKey="mykey")
        cloned = user.clone()
        assert cloned.authKey == "mykey"

    def test_clone_preserves_empty_priv_key(self):
        user = UsmUserData("testuser", authKey="mykey", privKey="mypriv")
        cloned = user.clone()
        assert cloned.privKey == "mypriv"

    def test_clone_preserves_auth_key_type_zero(self):
        """authKeyType=0 is falsy — must not be replaced by usmKeyTypePassphrase."""
        user = UsmUserData("testuser", authKey="mykey", authKeyType=0)
        cloned = user.clone()
        assert cloned.authKeyType == 0, (
            f"Expected authKeyType=0, got {cloned.authKeyType}. "
            "Old-style ternary may have replaced it with usmKeyTypePassphrase."
        )

    def test_clone_preserves_priv_key_type_zero(self):
        """privKeyType=0 is falsy — must not be replaced by usmKeyTypePassphrase."""
        user = UsmUserData("testuser", authKey="mykey", privKey="mypriv", privKeyType=0)
        cloned = user.clone()
        assert cloned.privKeyType == 0, (
            f"Expected privKeyType=0, got {cloned.privKeyType}. "
            "Old-style ternary may have replaced it with usmKeyTypePassphrase."
        )

    def test_clone_preserves_user_name(self):
        user = UsmUserData("testuser")
        cloned = user.clone()
        assert cloned.userName == "testuser"

    def test_clone_with_new_user_name(self):
        user = UsmUserData("testuser")
        cloned = user.clone(userName="newuser")
        assert cloned.userName == "newuser"

    def test_clone_preserves_security_name(self):
        user = UsmUserData("testuser", securityName="mysec")
        cloned = user.clone()
        assert cloned.securityName == "mysec"

    def test_clone_preserves_auth_protocol(self):
        user = UsmUserData("testuser", authKey="mykey")
        cloned = user.clone()
        assert cloned.authProtocol == user.authProtocol

    def test_clone_preserves_priv_protocol(self):
        user = UsmUserData("testuser", authKey="mykey", privKey="mypriv")
        cloned = user.clone()
        assert cloned.privProtocol == user.privProtocol
