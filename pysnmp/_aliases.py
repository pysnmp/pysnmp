#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
# License: https://github.com/pysnmp/pysnmp/blob/main/LICENSE.rst
#
"""Keeping the old camelCase spelling of the API working.

PySNMP's high-level API was camelCase, which PEP 8 does not call for. The
canonical spelling is snake_case now, and every renamed name keeps its old one
as an alias that warns and forwards.

The aliases are served by a module-level ``__getattr__`` (:pep:`562`) rather
than written into the namespace as assignments. That is what makes them
*deprecations* rather than second spellings: a plain ``getCmd = get_cmd`` binds
the old name in the module, so nothing can tell the two apart and no warning is
possible. Leaving the old name out of the namespace entirely means attribute
lookup misses, Python falls back to ``__getattr__``, and the alias gets a chance
to say it is on its way out.

The consequence is that an alias must not be assigned or imported into the
module it is served from -- doing so shadows ``__getattr__`` and silently turns
the deprecation back into an alias. :py:func:`install` therefore raises when a
name it is asked to serve is already bound.

PySMI does the same job for classes with its ``deprecated_camel_case``
decorator, and the warning text here matches it so the two projects read alike.
That decorator walks ``vars(cls)``, so it does not reach module-level functions
and values, which is what the high-level API is made of.
"""

import warnings
from collections.abc import Callable
from typing import Any

__all__ = ["install"]


def install(
    moduleName: str,
    namespace: dict[str, Any],
    aliases: dict[str, str],
) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """Build the ``__getattr__`` and ``__dir__`` a module needs to serve old names.

    Args:
        moduleName: the module's ``__name__``, used in the warning and the error.
        namespace: the module's ``globals()``, read when an alias is resolved.
        aliases: old camelCase name -> the snake_case name it now forwards to.

    Returns
    -------
        The two functions to bind as the module's ``__getattr__`` and ``__dir__``.

    Raises
    ------
        ValueError: if an alias is already bound in the namespace, where it would
            shadow ``__getattr__``, or if its target is missing.
    """
    for old, new in aliases.items():
        if old in namespace:
            raise ValueError(
                f"{moduleName}.{old} is bound in the module, so the deprecation "
                f"for it would never run. Remove the assignment or import; the "
                f"alias is served by __getattr__."
            )
        if new not in namespace:
            raise ValueError(
                f"{moduleName}.{old} is an alias for {new}, which the module "
                f"does not define."
            )

    def moduleGetattr(name: str) -> Any:
        """Serve a deprecated name, or report it as missing like any other."""
        new = aliases.get(name)
        if new is None:
            raise AttributeError(f"module {moduleName!r} has no attribute {name!r}")

        warnings.warn(
            f"{moduleName}.{name}() is deprecated and will be removed in a "
            f"future release; use {new}() instead",
            DeprecationWarning,
            stacklevel=2,
        )

        return namespace[new]

    def moduleDir() -> list[str]:
        """Both spellings, so the old ones stay discoverable while they last.

        Defining ``__dir__`` replaces the default listing rather than adding to
        it, so this has to name everything the module exports -- not just the
        aliases. A module with no ``__all__`` (``pysnmp.hlapi`` is one) would
        otherwise report the deprecated names as its entire contents.
        """
        exported = namespace.get("__all__")
        if exported is None:
            exported = [name for name in namespace if not name.startswith("_")]
        return sorted({*exported, *aliases})

    return moduleGetattr, moduleDir
