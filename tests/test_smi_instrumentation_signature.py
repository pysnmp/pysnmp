"""The instrumentation signature, and the adapter that keeps the old one working.

Managed objects take ``(varBind, **context)`` now. Subclassing
``MibScalarInstance`` is the documented way to implement an agent, so subclasses
written against the old ``(name, val, idx, acInfo)`` signature exist outside this
tree; they must keep serving requests, and must say they are on the way out.
"""

import warnings

import pytest

from pysnmp.proto import rfc1902
from pysnmp.smi import error, instrum
from pysnmp.smi._instrumcompat import (
    INSTRUMENTATION_METHODS,
    _controllerIsLegacy,
    _isLegacySignature,
    adaptLegacyInstrumentation,
    callInstrumentation,
)
from pysnmp.smi.builder import MibBuilder

mibBuilder = MibBuilder()
(MibScalarInstance,) = mibBuilder.importSymbols("SNMPv2-SMI", "MibScalarInstance")

TYPE_NAME = (1, 3, 6, 1, 2, 1, 1, 1)
INST_ID = (0,)
NAME = TYPE_NAME + INST_ID


def instanceOf(cls):
    return cls(TYPE_NAME, INST_ID, rfc1902.OctetString("x"))


def legacyInstance(**overrides):
    """A MibScalarInstance subclass written the old way."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)

        return type("Legacy", (MibScalarInstance,), overrides)


class TestSignatureDetection:
    def test_the_old_shape_is_detected(self):
        def readGet(self, name, val, idx, acInfo):
            pass

        assert _isLegacySignature(readGet)

    def test_the_new_shape_is_not(self):
        def readGet(self, varBind, **context):
            pass

        assert not _isLegacySignature(readGet)

    def test_the_test_is_about_shape_not_parameter_names(self):
        # A subclass may call its first argument whatever it likes; what marks
        # it current is that it can absorb the context.
        def readGet(self, binding, **anything):
            pass

        assert not _isLegacySignature(readGet)

    def test_something_uninspectable_is_left_alone(self):
        # Adapting wrongly would corrupt the call, so assume current and let
        # the call fail honestly rather than in the adapter.
        class Uninspectable:
            __call__ = None

        assert not _isLegacySignature(Uninspectable())


class TestAdapterInstallation:
    def test_a_legacy_subclass_warns_once_at_definition(self):
        with pytest.warns(DeprecationWarning, match="deprecated .* signature"):
            type(
                "Legacy",
                (MibScalarInstance,),
                {"readGet": lambda self, name, val, idx, acInfo: (name, val)},
            )

    def test_the_warning_names_the_methods_it_adapted(self):
        with pytest.warns(DeprecationWarning, match="readGet, writeTest"):
            type(
                "Legacy",
                (MibScalarInstance,),
                {
                    "readGet": lambda self, name, val, idx, acInfo: (name, val),
                    "writeTest": lambda self, name, val, idx, acInfo: None,
                },
            )

    def test_a_current_subclass_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            type(
                "Current",
                (MibScalarInstance,),
                {"readGet": lambda self, varBind, **context: varBind},
            )

    def test_a_subclass_overriding_nothing_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            type("Plain", (MibScalarInstance,), {})

    def test_detection_runs_once_per_class_not_per_call(self):
        # The adapter is installed on the class; nothing is inspected while a
        # request is being served.
        cls = legacyInstance(
            readGet=lambda self, name, val, idx, acInfo: (name, val),
        )
        adapted = cls.__dict__["readGet"]

        instance = instanceOf(cls)
        for _ in range(3):
            instance.readGet((NAME, None), idx=0)

        assert cls.__dict__["readGet"] is adapted

    def test_adapting_twice_does_not_double_wrap(self):
        cls = legacyInstance(
            readGet=lambda self, name, val, idx, acInfo: (name, val),
        )
        adapted = cls.__dict__["readGet"]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            adaptLegacyInstrumentation(cls)

        assert cls.__dict__["readGet"] is adapted


class TestLegacySubclassStillWorks:
    """The promise: a subclass written for 5.0 keeps serving, unmodified."""

    def test_read_get_receives_the_old_arguments(self):
        seen = {}

        def readGet(self, name, val, idx, acInfo):
            seen.update(name=name, val=val, idx=idx, acInfo=acInfo)
            return name, rfc1902.OctetString("served")

        instance = instanceOf(legacyInstance(readGet=readGet))

        acFun, acCtx = object(), object()
        result = instance.readGet((NAME, None), idx=7, acFun=acFun, acCtx=acCtx)

        assert seen["name"] == NAME
        assert seen["idx"] == 7
        assert seen["acInfo"] == (acFun, acCtx)
        assert result[1] == rfc1902.OctetString("served")

    def test_the_next_methods_still_receive_oName_positionally(self):
        seen = {}

        def readGetNext(self, name, val, idx, acInfo, oName=None):
            seen["oName"] = oName
            return name, rfc1902.OctetString("next")

        instance = instanceOf(legacyInstance(readGetNext=readGetNext))
        instance.readGetNext((NAME, None), idx=0, oName=(1, 3, 6))

        assert seen["oName"] == (1, 3, 6)

    def test_a_legacy_write_still_raises_what_it_raised(self):
        def writeTest(self, name, val, idx, acInfo):
            raise error.NotWritableError(idx=idx, name=name)

        instance = instanceOf(legacyInstance(writeTest=writeTest))

        with pytest.raises(error.NotWritableError):
            instance.writeTest((NAME, rfc1902.OctetString("y")), idx=0)

    def test_missing_context_entries_arrive_as_None(self):
        # A caller reaching the object directly need not supply everything.
        seen = {}

        def readGet(self, name, val, idx, acInfo):
            seen.update(idx=idx, acInfo=acInfo)
            return name, val

        instance = instanceOf(legacyInstance(readGet=readGet))
        instance.readGet((NAME, None))

        assert seen["idx"] is None
        assert seen["acInfo"] == (None, None)


class TestCurrentSubclass:
    def test_a_current_subclass_receives_the_context(self):
        seen = {}

        class Current(MibScalarInstance):
            def readGet(self, varBind, **context):
                seen.update(varBind=varBind, context=context)
                return varBind

        instance = instanceOf(Current)
        instance.readGet((NAME, None), idx=3, acFun=None, acCtx=None)

        assert seen["varBind"] == (NAME, None)
        assert seen["context"]["idx"] == 3

    def test_a_current_subclass_is_not_wrapped(self):
        class Current(MibScalarInstance):
            def readGet(self, varBind, **context):
                return varBind

        assert not getattr(
            Current.__dict__["readGet"], "__pysnmpLegacyInstrumentation__", False
        )


class TestBuiltInNodesAreCurrent:
    @pytest.mark.parametrize("methodName", INSTRUMENTATION_METHODS)
    def test_no_built_in_node_is_being_adapted(self, methodName):
        # If one were, the conversion missed it and every request through that
        # node would be paying for an adapter it should not need.
        symbols = (
            "MibTree",
            "MibScalar",
            "MibScalarInstance",
            "MibTableColumn",
            "MibTableRow",
            "MibTable",
        )
        for symbol in symbols:
            (cls,) = mibBuilder.importSymbols("SNMPv2-SMI", symbol)
            func = cls.__dict__.get(methodName)
            if func is None:
                continue
            assert not getattr(func, "__pysnmpLegacyInstrumentation__", False), (
                f"{symbol}.{methodName} is being adapted"
            )


class TestDuckTypedController:
    """The controller contract is duck-typed, so it cannot be hooked at class
    creation: the command responder calls whatever object it was handed, and an
    implementation need not inherit from anything. It is decided at the call
    site instead.
    """

    def setup_method(self):
        _controllerIsLegacy.clear()

    def test_a_legacy_duck_typed_controller_is_adapted(self):
        seen = {}

        class Legacy:
            def readVars(self, varBinds, acInfo=(None, None)):
                seen["acInfo"] = acInfo
                return [(varBinds[0][0], rfc1902.OctetString("legacy"))]

        acFun, acCtx = object(), object()

        with pytest.warns(DeprecationWarning, match=r"readVars\(\) implements"):
            result = callInstrumentation(
                Legacy().readVars, [(NAME, None)], acFun=acFun, acCtx=acCtx
            )

        assert seen["acInfo"] == (acFun, acCtx)
        assert result[0][1] == rfc1902.OctetString("legacy")

    def test_a_current_duck_typed_controller_is_called_directly(self):
        seen = {}

        class Current:
            def readVars(self, varBinds, **context):
                seen["context"] = context
                return [(varBinds[0][0], rfc1902.OctetString("current"))]

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            result = callInstrumentation(
                Current().readVars, [(NAME, None)], acFun=None, acCtx="ctx"
            )

        assert seen["context"]["acCtx"] == "ctx"
        assert result[0][1] == rfc1902.OctetString("current")

    def test_the_shape_is_decided_once_per_class(self):
        calls = []

        class Legacy:
            def readVars(self, varBinds, acInfo=(None, None)):
                calls.append(acInfo)
                return []

        controller = Legacy()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            for _ in range(3):
                callInstrumentation(controller.readVars, [(NAME, None)])

        assert len(calls) == 3
        assert list(_controllerIsLegacy) == [(Legacy, "readVars")]

    def test_the_built_in_controller_is_current(self):
        # If it were not, every request would be paying for an adapter.
        assert not _isLegacySignature(instrum.MibInstrumController.readVars)
        assert not _isLegacySignature(instrum.AbstractMibInstrumController.readVars)


class TestLegacySubclassThroughTheController:
    """The acceptance criterion from #279: a subclass written against the 5.0
    signature serves real requests unmodified, through the real controller.
    """

    @staticmethod
    def _agent(**overrides):
        """A MIB with one legacy-signature scalar instance under sysDescr."""
        builder_ = MibBuilder()
        builder_.loadModules("SNMPv2-MIB")
        (scalarInstance,) = builder_.importSymbols("SNMPv2-SMI", "MibScalarInstance")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cls = type("LegacyScalar", (scalarInstance,), overrides)

        builder_.exportSymbols(
            "__TEST-MIB",
            cls(TYPE_NAME, INST_ID, rfc1902.OctetString("initial")),
        )

        from pysnmp.smi import instrum as _instrum

        return _instrum.MibInstrumController(builder_), caught

    def test_it_warns_exactly_once_for_the_class(self):
        _, caught = self._agent(
            readGet=lambda self, name, val, idx, acInfo: (name, val),
        )
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]

        assert len(deprecations) == 1

    def test_get_is_served_by_the_legacy_method(self):
        seen = []

        def readGet(self, name, val, idx, acInfo):
            seen.append((name, idx, acInfo))
            return name, rfc1902.OctetString("served")

        controller, _ = self._agent(readGet=readGet)

        result = controller.readVars([(NAME, None)], acFun=None, acCtx="ctx")

        assert result[0][1] == rfc1902.OctetString("served")
        assert seen[0][1] == 0  # idx reached it
        assert seen[0][2] == (None, "ctx")  # and so did acInfo

    def test_get_next_is_served_by_the_legacy_method(self):
        def readGetNext(self, name, val, idx, acInfo, oName=None):
            # The walk hands the original name down; without it a walk cannot
            # tell it has already passed this instance.
            assert oName is not None
            return name, rfc1902.OctetString("walked")

        controller, _ = self._agent(
            readTestNext=lambda self, name, val, idx, acInfo, oName=None: None,
            readGetNext=readGetNext,
        )

        result = controller.readNextVars([(TYPE_NAME, None)])

        assert result[0][1] == rfc1902.OctetString("walked")

    def test_set_is_served_by_the_legacy_methods(self):
        committed = []

        def writeTest(self, name, val, idx, acInfo):
            return None

        def writeCommit(self, name, val, idx, acInfo):
            committed.append((name, val))
            self.syntax = self.syntax.clone(val)

        controller, _ = self._agent(
            writeTest=writeTest,
            writeCommit=writeCommit,
            writeCleanup=lambda self, name, val, idx, acInfo: None,
        )

        controller.writeVars([(NAME, rfc1902.OctetString("written"))])

        assert committed[0][1] == rfc1902.OctetString("written")
