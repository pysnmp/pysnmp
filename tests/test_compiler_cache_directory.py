"""Where compiled MIBs land when no ``destination=`` says.

Compiled MIBs are regenerable, user-specific and non-essential, so they belong
in the platform's cache, not in a dotdir that a home-directory backup carries
around forever. Each platform has its own answer, and the XDG Base Directory
specification is the one for Linux and the BSDs.

The part that has to hold above all is the migration rule: an existing
``~/.pysnmp/mibs`` keeps being used, so that upgrading pysnmp does not orphan a
populated cache and quietly recompile everything in it.
"""

from pathlib import Path

import pytest

from pysnmp.smi.compiler import (
    CACHE_HOME_ENV,
    LOCAL_APP_DATA_ENV,
    cacheDirectory,
    defaultDest,
)


class TestLegacyDirectoryWins:
    """A cache someone already has is not orphaned by an upgrade."""

    def test_an_existing_posix_dotdir_is_kept(self, tmp_path):
        legacy = tmp_path / ".pysnmp" / "mibs"
        legacy.mkdir(parents=True)

        assert cacheDirectory(home=tmp_path, platform="linux", environ={}) == str(
            legacy
        )

    def test_an_existing_dotdir_beats_an_explicit_xdg_cache_home(self, tmp_path):
        # Otherwise setting XDG_CACHE_HOME -- which is about where new cache
        # goes -- would silently discard the cache already on disk.
        legacy = tmp_path / ".pysnmp" / "mibs"
        legacy.mkdir(parents=True)

        assert cacheDirectory(
            home=tmp_path,
            platform="linux",
            environ={CACHE_HOME_ENV: str(tmp_path / "xdg")},
        ) == str(legacy)

    def test_an_existing_windows_directory_is_kept(self, tmp_path):
        legacy = tmp_path / "PySNMP Configuration" / "mibs"
        legacy.mkdir(parents=True)

        assert cacheDirectory(
            home=tmp_path,
            platform="win32",
            environ={LOCAL_APP_DATA_ENV: str(tmp_path / "AppData" / "Local")},
        ) == str(legacy)

    def test_a_dotfile_of_that_name_is_not_a_cache(self, tmp_path):
        # Only a directory counts. A stray file cannot be compiled into, and
        # treating it as the destination would fail at the first write.
        (tmp_path / ".pysnmp").write_text("not a directory")

        assert cacheDirectory(home=tmp_path, platform="linux", environ={}) == str(
            tmp_path / ".cache" / "pysnmp" / "mibs"
        )


class TestXdgOnLinux:
    """The spec, on the platforms it is the convention for."""

    def test_unset_falls_back_to_dot_cache(self, tmp_path):
        assert cacheDirectory(home=tmp_path, platform="linux", environ={}) == str(
            tmp_path / ".cache" / "pysnmp" / "mibs"
        )

    def test_set_is_honoured(self, tmp_path):
        # An absolute path in the *host's* terms, for the reason
        # `TestWindows.test_local_app_data_is_used` spells out: absoluteness is
        # judged under the interpreter's own rules, and since Python 3.13 those
        # no longer count a driveless "/somewhere/else" as absolute on Windows,
        # where this suite also runs.
        elsewhere = tmp_path / "elsewhere"

        assert cacheDirectory(
            home=tmp_path,
            platform="linux",
            environ={CACHE_HOME_ENV: str(elsewhere)},
        ) == str(elsewhere / "pysnmp" / "mibs")

    def test_empty_is_treated_as_unset(self, tmp_path):
        # "If $XDG_CACHE_HOME is either not set or empty, a default equal to
        # $HOME/.cache should be used."
        assert cacheDirectory(
            home=tmp_path, platform="linux", environ={CACHE_HOME_ENV: ""}
        ) == str(tmp_path / ".cache" / "pysnmp" / "mibs")

    def test_a_relative_path_is_ignored(self, tmp_path):
        # "All paths set in these environment variables must be absolute. If an
        # implementation encounters a relative path in any of these variables
        # it should consider the path invalid and ignore it."
        assert cacheDirectory(
            home=tmp_path, platform="linux", environ={CACHE_HOME_ENV: "relative/cache"}
        ) == str(tmp_path / ".cache" / "pysnmp" / "mibs")

    @pytest.mark.parametrize("platform", ["freebsd14", "openbsd7", "sunos5"])
    def test_the_other_posix_platforms_follow_the_same_rule(self, platform, tmp_path):
        assert cacheDirectory(home=tmp_path, platform=platform, environ={}) == str(
            tmp_path / ".cache" / "pysnmp" / "mibs"
        )


class TestMacOS:
    """Its own convention, but an explicit setting still means something."""

    def test_the_default_is_library_caches(self, tmp_path):
        assert cacheDirectory(home=tmp_path, platform="darwin", environ={}) == str(
            tmp_path / "Library" / "Caches" / "pysnmp" / "mibs"
        )

    def test_an_explicit_xdg_cache_home_is_honoured(self, tmp_path):
        # Not the platform convention, but someone who set it meant it. Host
        # absolute, for the reason `TestXdgOnLinux.test_set_is_honoured` gives.
        elsewhere = tmp_path / "elsewhere"

        assert cacheDirectory(
            home=tmp_path,
            platform="darwin",
            environ={CACHE_HOME_ENV: str(elsewhere)},
        ) == str(elsewhere / "pysnmp" / "mibs")


class TestWindows:
    """LOCALAPPDATA, with the segment that says this is cache."""

    def test_local_app_data_is_used(self, tmp_path):
        # An absolute path in the *host's* terms, because the absoluteness
        # check runs under the interpreter's own rules and this suite runs on
        # POSIX too. In production the injected platform is always the running
        # one, so the two never disagree; here they would.
        localAppData = tmp_path / "elsewhere" / "Local"

        assert cacheDirectory(
            home=tmp_path,
            platform="win32",
            environ={LOCAL_APP_DATA_ENV: str(localAppData)},
        ) == str(localAppData / "pysnmp" / "Cache" / "mibs")

    def test_unset_falls_back_under_the_home_directory(self, tmp_path):
        assert cacheDirectory(home=tmp_path, platform="win32", environ={}) == str(
            tmp_path / "AppData" / "Local" / "pysnmp" / "Cache" / "mibs"
        )

    def test_xdg_cache_home_does_not_apply(self, tmp_path):
        # XDG is not a Windows convention, and a WSL-inherited value pointing
        # at a Linux path would be a poor destination for a Windows process.
        assert cacheDirectory(
            home=tmp_path,
            platform="win32",
            environ={CACHE_HOME_ENV: "/home/someone/.cache"},
        ) == str(tmp_path / "AppData" / "Local" / "pysnmp" / "Cache" / "mibs")


class TestTheModuleDefault:
    """`defaultDest` is what `addMibCompiler` actually uses."""

    def test_it_is_settled_once_at_import(self):
        # Not a property recomputed per read: the destination must not change
        # under a running application because something touched $HOME.
        assert isinstance(defaultDest, str)
        assert defaultDest.endswith("mibs")

    def test_it_agrees_with_the_helper(self):
        assert defaultDest == cacheDirectory()

    def test_it_is_no_longer_the_bare_dotdir(self):
        # The defect: a regenerable cache sitting in $HOME, where every
        # home-directory backup picks it up.
        assert (
            defaultDest != str(Path.home() / ".pysnmp" / "mibs")
            or (Path.home() / ".pysnmp" / "mibs").is_dir()
        )
