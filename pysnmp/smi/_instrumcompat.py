#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
# License: https://github.com/pysnmp/pysnmp/blob/main/LICENSE.rst
#
"""Keeping MIB instrumentation written against the old signature working.

The instrumentation methods a managed object implements used to take
``(name, val, idx, acInfo)``. They take ``(varBind, **context)`` now, which is
what lets information be threaded down to them without another positional
argument every time something new needs to travel -- an awaitable among them,
which is the prerequisite for asynchronous instrumentation.

Subclassing :py:class:`~pysnmp.smi.mibs.SNMPv2-SMI.MibScalarInstance` is the
documented way to implement an agent, so subclasses written against the old
signature exist and must keep working. :py:func:`adaptLegacyInstrumentation`
finds them and installs an adapter that translates the call.

The same applies one level up, to ``readVars``/``readNextVars``/``writeVars``,
which took ``acInfo`` as a second positional argument. That contract is
**duck-typed**: the command responder calls whatever object it was handed, and
an implementation need not inherit from
:py:class:`~pysnmp.smi.instrum.AbstractMibInstrumController` at all -- this
repository's own snmpsim stand-in does not. So there is no class creation to
hook, and :py:func:`callInstrumentation` decides at the call site instead,
once per class and cached.

The detection runs **once per class**, when the class is created, and what it
decides is baked into the class then. Nothing is inspected while a request is
being served: a subclass on the new signature is untouched and pays nothing at
all, and one on the old signature pays a single extra call per access.
"""

import functools
import inspect
import warnings
from collections.abc import Callable
from inspect import isawaitable
from typing import Any

__all__ = [
    "adaptLegacyInstrumentation",
    "awaitInstrumentation",
    "callInstrumentation",
]

#: The instrumentation methods whose signature changed. A subclass overriding
#: any of them is what this module exists to find.
INSTRUMENTATION_METHODS: tuple[str, ...] = (
    "readTest",
    "readGet",
    "readTestNext",
    "readGetNext",
    "writeTest",
    "writeCommit",
    "writeCleanup",
    "writeUndo",
    "createTest",
    "createCommit",
    "createCleanup",
    "createUndo",
    "destroyTest",
    "destroyCommit",
    "destroyCleanup",
    "destroyUndo",
)


def _isLegacySignature(func: Callable[..., Any]) -> bool:
    """Whether *func* was written against ``(name, val, idx, acInfo)``.

    The new signature ends in ``**context`` and the old one does not, which is
    the whole test. It is deliberately about the shape rather than the parameter
    names: a subclass is free to call its first argument whatever it likes, and
    a method that can absorb keyword arguments can be handed them.
    """
    try:
        parameters = inspect.signature(func).parameters
    except (TypeError, ValueError):
        # Something not introspectable -- a builtin, or an object with an
        # unusual __call__. Assume it is current rather than adapting it
        # wrongly, which would corrupt the call.
        return False

    return not any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


#: The two methods the old signature gave a fifth positional argument to: the
#: name the walk started from.
_ONAME_METHODS = frozenset({"readTestNext", "readGetNext"})


def _takesOName(func: Callable[..., Any], methodName: str) -> bool:
    """Whether this legacy method wants the walk's original name passed to it.

    The old signature always put it fifth and positionally, so what decides this
    is whether the method can take a fifth positional argument -- not whether it
    happens to spell it ``oName``. A passthrough written ``(self, *args)`` wants
    it, and so does one that renamed the parameter; reading the name alone would
    leave the first silently short of an argument and raise TypeError at the
    second.
    """
    if methodName not in _ONAME_METHODS:
        return False

    parameters = list(inspect.signature(func).parameters.values())

    if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in parameters):
        return True

    positional = sum(
        1
        for p in parameters
        if p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    )

    # self, name, val, idx, acInfo, oName
    return positional >= 6


def _adapt(func: Callable[..., Any], takesOName: bool) -> Callable[..., Any]:
    """Wrap a legacy method so that it can be called with the new signature."""

    @functools.wraps(func)
    def adapted(self: Any, varBind: Any, **context: Any) -> Any:
        name, val = varBind
        acInfo = (context.get("acFun"), context.get("acCtx"))
        idx = context.get("idx")

        if takesOName:
            return func(self, name, val, idx, acInfo, context.get("oName"))

        return func(self, name, val, idx, acInfo)

    adapted.__pysnmpLegacyInstrumentation__ = True  # type: ignore[attr-defined]

    return adapted


def adaptLegacyInstrumentation(cls: type) -> None:
    """Install adapters for any instrumentation this class declares the old way.

    Only methods defined on *cls* itself are considered: an inherited one has
    already been dealt with on the class that declared it.

    Args:
        cls: the managed-object class just created.
    """
    adapted = []

    for methodName in INSTRUMENTATION_METHODS:
        func = cls.__dict__.get(methodName)

        if func is None or not callable(func):
            continue

        if getattr(func, "__pysnmpLegacyInstrumentation__", False):
            continue

        if not _isLegacySignature(func):
            continue

        # `oName` travels in the context now, but the old signature took it
        # positionally and only the *Next methods had it.
        setattr(cls, methodName, _adapt(func, _takesOName(func, methodName)))
        adapted.append(methodName)

    if not adapted:
        return

    warnings.warn(
        f"{cls.__module__}.{cls.__qualname__} implements MIB instrumentation "
        f"with the deprecated (name, val, idx, acInfo) signature: "
        f"{', '.join(adapted)}. These are adapted for now and will stop being "
        f"adapted in a future release; use (varBind, **context) instead, where "
        f"varBind is an (ObjectName, value) pair and context carries idx, acFun "
        f"and acCtx.",
        DeprecationWarning,
        stacklevel=3,
    )


#: How a given controller class wants its operations called. Keyed by class and
#: method name, so the decision is made once rather than per request.
_controllerIsLegacy: dict[tuple[type, str], bool] = {}


def callInstrumentation(
    mgmtFun: Callable[..., Any], varBinds: Any, **context: Any
) -> Any:
    """Call one instrumentation operation, adapting one written the old way.

    ``readVars``/``readNextVars``/``writeVars`` take ``(varBinds, **context)``
    now and took ``(varBinds, acInfo)`` before. Unlike the managed-object
    methods, this contract is duck-typed -- an implementation is whatever object
    was handed to the command responder, inheriting from nothing in particular
    -- so the shape is worked out here rather than when a class is created.

    The answer is cached against the class, so the signature is inspected once
    however many requests follow.

    Args:
        mgmtFun: the bound operation to call.
        varBinds: the bindings to operate on.
        **context: what the operation is given, including `acFun` and `acCtx`.

    Returns
    -------
        Whatever the operation returned.
    """
    owner = type(getattr(mgmtFun, "__self__", mgmtFun))
    key = (owner, getattr(mgmtFun, "__name__", ""))

    isLegacy = _controllerIsLegacy.get(key)

    if isLegacy is None:
        isLegacy = _isLegacySignature(mgmtFun)
        _controllerIsLegacy[key] = isLegacy

        if isLegacy:
            warnings.warn(
                f"{owner.__module__}.{owner.__qualname__}.{key[1]}() implements "
                f"the MIB instrumentation contract with the deprecated "
                f"(varBinds, acInfo) signature. It is adapted for now and will "
                f"stop being adapted in a future release; use "
                f"(varBinds, **context) instead, where context carries acFun "
                f"and acCtx.",
                DeprecationWarning,
                stacklevel=2,
            )

    if isLegacy:
        return mgmtFun(varBinds, (context.get("acFun"), context.get("acCtx")))

    return mgmtFun(varBinds, **context)


async def awaitInstrumentation(result: Any) -> Any:
    """What an instrumentation operation produced, waited on if it has to be.

    A controller may serve values from somewhere that has to be waited on, in
    which case its operations are coroutines and what
    :py:func:`callInstrumentation` hands back is not the answer but the means of
    getting it. This tells the two apart so a caller that is already in a
    coroutine does not have to.
    """
    if isawaitable(result):
        return await result
    return result
