"""The camelCase spellings, and the deprecation that keeps them honest.

The old names must keep working -- that is the whole promise -- but they have to
say they are on the way out, which a plain assignment cannot do. These tests pin
both halves, and the shape of the mechanism that makes it possible.
"""

import warnings

import pytest

from pysnmp import _aliases

# (module, old camelCase name, the snake_case name it forwards to)
RENAMED = [
    ("pysnmp.hlapi", "getCmd", "get_cmd"),
    ("pysnmp.hlapi", "nextCmd", "next_cmd"),
    ("pysnmp.hlapi", "setCmd", "set_cmd"),
    ("pysnmp.hlapi", "bulkCmd", "bulk_cmd"),
    ("pysnmp.hlapi", "sendNotification", "send_notification"),
    ("pysnmp.hlapi", "getDeviceReport", "get_device_report"),
    ("pysnmp.hlapi", "dhKeyChange", "dh_key_change"),
    ("pysnmp.hlapi.asyncio", "getCmd", "get_cmd"),
    ("pysnmp.hlapi.asyncio", "nextCmd", "next_cmd"),
    ("pysnmp.hlapi.asyncio", "setCmd", "set_cmd"),
    ("pysnmp.hlapi.asyncio", "bulkCmd", "bulk_cmd"),
    ("pysnmp.hlapi.asyncio", "isEndOfMib", "is_end_of_mib"),
    ("pysnmp.hlapi.asyncio", "sendNotification", "send_notification"),
    ("pysnmp.hlapi.asyncio", "getDeviceReport", "get_device_report"),
    ("pysnmp.hlapi.asyncio", "dhKeyChange", "dh_key_change"),
    ("pysnmp.hlapi.asyncio.cmdgen", "getCmd", "get_cmd"),
    ("pysnmp.hlapi.asyncio.ntforg", "sendNotification", "send_notification"),
    ("pysnmp.hlapi.asyncio.device", "getDeviceReport", "get_device_report"),
    ("pysnmp.hlapi.asyncio.dh", "dhKeyChange", "dh_key_change"),
    ("pysnmp.hlapi.asyncio.sync", "getCmd", "get_cmd"),
    ("pysnmp.hlapi.asyncio.sync.cmdgen", "bulkCmd", "bulk_cmd"),
    ("pysnmp.hlapi.asyncio.sync.device", "getDeviceReport", "get_device_report"),
    ("pysnmp.hlapi.asyncio.sync.dh", "dhKeyChange", "dh_key_change"),
]


def _module(name):
    return __import__(name, fromlist=["__name__"])


@pytest.mark.parametrize(("moduleName", "old", "new"), RENAMED)
class TestRenamedNames:
    def test_the_old_name_still_resolves_to_the_new_one(self, moduleName, old, new):
        module = _module(moduleName)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert getattr(module, old) is getattr(module, new)

    def test_the_old_name_warns(self, moduleName, old, new):
        module = _module(moduleName)
        with pytest.warns(DeprecationWarning, match=rf"\b{old}\(\) is deprecated"):
            getattr(module, old)

    def test_the_warning_names_the_replacement(self, moduleName, old, new):
        module = _module(moduleName)
        with pytest.warns(DeprecationWarning, match=rf"use {new}\(\) instead"):
            getattr(module, old)

    def test_the_new_name_does_not_warn(self, moduleName, old, new):
        module = _module(moduleName)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            getattr(module, new)

    def test_both_spellings_are_discoverable(self, moduleName, old, new):
        names = dir(_module(moduleName))
        assert old in names
        assert new in names

    def test_only_the_new_name_is_exported(self, moduleName, old, new):
        # __all__ is what `import *` and the documentation follow, so the
        # deprecated spelling must not be in it.
        exported = getattr(_module(moduleName), "__all__", None)
        if exported is not None:
            assert new in exported
            assert old not in exported


class TestImportingTheOldName:
    def test_from_import_warns_too(self):
        # `from x import y` falls back to getattr, so it goes through the same
        # path -- this is the shape most callers will actually have written.
        with pytest.warns(DeprecationWarning, match=r"getCmd\(\) is deprecated"):
            from pysnmp.hlapi import getCmd  # noqa: F401


class TestUnknownNames:
    def test_a_name_that_never_existed_still_raises_attribute_error(self):
        import pysnmp.hlapi as hlapi

        with pytest.raises(AttributeError, match="has no attribute 'noSuchThing'"):
            hlapi.noSuchThing  # noqa: B018 - the lookup is the assertion

    def test_the_error_names_the_module(self):
        import pysnmp.hlapi.asyncio as hlapi_asyncio

        with pytest.raises(AttributeError, match="pysnmp.hlapi.asyncio"):
            hlapi_asyncio.noSuchThing  # noqa: B018 - the lookup is the assertion


class TestInstall:
    """The guardrails on the mechanism itself."""

    def test_an_alias_already_bound_is_refused(self):
        # A plain `getCmd = get_cmd` shadows __getattr__, which would silently
        # turn the deprecation back into a second spelling. That is the failure
        # this mechanism exists to prevent, so it must not be quiet.
        namespace = {"get_cmd": object(), "getCmd": object()}
        with pytest.raises(ValueError, match="would never run"):
            _aliases.install("m", namespace, {"getCmd": "get_cmd"})

    def test_an_alias_pointing_at_nothing_is_refused(self):
        with pytest.raises(ValueError, match="does not define"):
            _aliases.install("m", {}, {"getCmd": "get_cmd"})

    def test_dir_keeps_the_rest_of_the_module(self):
        # __dir__ replaces the default listing rather than adding to it, so a
        # module with no __all__ must still report everything it exports.
        namespace = {"get_cmd": object(), "SomethingElse": object(), "_private": 1}
        _, moduleDir = _aliases.install("m", namespace, {"getCmd": "get_cmd"})
        assert moduleDir() == ["SomethingElse", "getCmd", "get_cmd"]

    def test_dir_follows_all_when_there_is_one(self):
        namespace = {"get_cmd": object(), "Hidden": object(), "__all__": ["get_cmd"]}
        _, moduleDir = _aliases.install("m", namespace, {"getCmd": "get_cmd"})
        assert moduleDir() == ["getCmd", "get_cmd"]
