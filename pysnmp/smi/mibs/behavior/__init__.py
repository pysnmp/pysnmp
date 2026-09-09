"""Hand-written runtime behavior for MIB modules pysnmp does not generate.

A MIB module is Python rendered from ASN.1, and the ASN.1 does not state
everything the runtime needs. RFC 4001 section 4 is the canonical case: how an
``InetAddress`` index is encoded depends on the value of the
``InetAddressType`` index preceding it in the same row, a relation SMIv2 has no
syntax for and that the RFC states in a DESCRIPTION clause, in prose. No code
generator can read that off the module.

pysnmp used to carry such relations by hand-editing the generated module and
never regenerating it. Five modules sat that way from April 2017 to 2026 --
see pysnmp/pysmi#231 -- until the edits were separated from the generated code
they were tangled with.

This package holds them, one file per module named exactly as the module plus
``.py``. :py:func:`apply` runs a fragment in the namespace of the module that
was just loaded, after the module built its objects, so the fragment reaches
every symbol the module defined by name and the generated half stays
regenerable.

Why here rather than in pysmi: a fragment is engine behavior, not MIB
semantics. It names pysnmp's exception types, pysnmp's socket-address
convention, pysnmp's enterprise number. pysmi compiles ASN.1 and has other
back ends; the moment a fragment lives there, pysmi carries policy belonging to
one of its consumers, and a behavior fix waits on a pysmi release. Both
happened. See the equivalent directory in pysmi, which this replaces.

What belongs here
-----------------

A runtime relation the ASN.1 cannot state, and that therefore no code
generator can derive.

What does not
-------------

Anything derivable from the module. If the SYNTAX, DISPLAY-HINT, SIZE clause or
IMPORTS already determine something the generator is not emitting, that is a
code generator bug and the fix goes upstream in ``pysmi/codegen/``. A fragment
that papers over it hides the bug for one module and leaves every other module
wrong.

Writing one
-----------

The fragment is executed, not imported: it has no module scope of its own, and
its names land in the loaded module's namespace beside the symbols the MIB
defines. So

- prefix every helper with ``_``, and alias every import (``import os as _os``),
  so a fragment cannot shadow a symbol the MIB defines;
- attach methods after the class -- ``Foo.prettyIn = _prettyIn`` -- since the
  class body is generated and closed by then. Zero-argument ``super()`` does
  not work in a function defined outside a class body: name the base
  explicitly, ``TextualConvention.prettyIn(self, value)``;
- do not rely on private name mangling. ``self.__x`` inside a function defined
  outside a class body is ``self.__x``, not ``self._Foo__x``;
- re-seed anything already built from a class attribute the fragment sets. A
  fragment runs after the module constructed its objects, so setting an
  attribute the constructor reads -- ``defaultValue``, ``subtypeSpec`` -- fixes
  the class and leaves every instance made from it as it was.
  ``SNMP-FRAMEWORK-MIB`` sets ``SnmpEngineID.defaultValue`` and so rebuilds
  ``snmpEngineID.syntax`` after it. See pysnmp/pysmi#236;
- cite the RFC and section that states the relation, in a comment at the top;
- keep it idempotent. pysmi splices its own copy of these fragments into the
  modules it bundles, so until that stops both run, this one last.
"""

import os
from typing import Any

#: What a fragment is named: the module, then this.
_SUFFIX = ".py"

_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

_cache: dict[str, str] | None = None


def _fragments() -> dict[str, str]:
    """Every fragment this package carries, keyed by module name."""
    global _cache

    if _cache is None:
        found = {}

        for entry in os.listdir(_DIRECTORY):
            if not entry.endswith(_SUFFIX) or entry.startswith("__"):
                continue

            found[entry[: -len(_SUFFIX)]] = os.path.join(_DIRECTORY, entry)

        _cache = found

    return _cache


def modules() -> frozenset[str]:
    """The modules a fragment is carried for."""
    return frozenset(_fragments())


def source(module: str) -> str:
    """The fragment for ``module``, or an empty string if there is none."""
    path = _fragments().get(module)

    if path is None:
        return ""

    with open(path, encoding="utf-8") as fileObj:
        return fileObj.read()


def apply(module: str, namespace: dict[str, Any]) -> bool:
    """Run ``module``'s fragment, if it has one, in ``namespace``.

    Args:
        module: the MIB module just loaded
        namespace: the loaded module's globals -- what its own symbols are
            bound in, which is what the fragment reads and writes

    Returns
    -------
        Whether a fragment ran.
    """
    path = _fragments().get(module)

    if path is None:
        return False

    with open(path, encoding="utf-8") as fileObj:
        text = fileObj.read()

    # Compiled against the fragment's own path so a traceback out of one points
    # at the file to edit rather than at a string.
    exec(compile(text, path, "exec"), namespace)  # noqa: S102

    return True
