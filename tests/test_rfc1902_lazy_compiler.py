"""The MIB compiler is imported when it is used, not when rfc1902 is imported.

``pysnmp.smi.compiler`` imports pysmi at module level, which transitively pulls
in ``requests``, ``urllib3``, ``certifi``, ``idna``, ``charset_normalizer``,
``ssl`` and ``socket``, plus pysmi's ASN.1 lexer and parser tables. Every
consumer of ``ObjectIdentity`` / ``ObjectType`` / ``NotificationType`` paid that
cost, including managers and trap receivers that never compile a MIB.

Nothing at import time uses ``addMibCompiler``: it is referenced only inside
``ObjectIdentity.resolveWithMib()``. So the import belongs at the call site.

Two things are asserted here, and they pull in opposite directions:

* the cost is actually deferred -- a fresh interpreter that imports
  ``pysnmp.smi.rfc1902`` must not have pysmi in ``sys.modules``
* nothing else changed -- ``resolveWithMib()`` still attaches a compiler, with
  the same arguments, on both of its branches

Without the second set the first is trivially satisfiable by breaking
resolution. See pysnmp/pysnmp#140.
"""

import subprocess
import sys
import textwrap

import pytest

from pysnmp.smi import builder, rfc1902, view
from pysnmp.smi.rfc1902 import ObjectIdentity


def _fresh_interpreter(body: str) -> str:
    """Run *body* in a new interpreter and return its stdout.

    A subprocess rather than ``importlib.reload``: pysmi is imported by other
    tests in this suite and by pysnmp's own MIB loading, so ``sys.modules`` in
    this process says nothing about what importing rfc1902 costs on its own.
    """
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(body)],
        capture_output=True,
        text=True,
        check=True,
    )

    return completed.stdout.strip()


class TestImportIsDeferred:
    """Importing the module must not import the compiler."""

    def test_import_does_not_load_pysmi(self):
        """No pysmi module is imported by ``import pysnmp.smi.rfc1902``."""
        loaded = _fresh_interpreter(
            """
            import sys
            import pysnmp.smi.rfc1902  # noqa: F401

            print(",".join(sorted(
                m for m in sys.modules
                if m == "pysmi" or m.startswith("pysmi.")
            )))
            """
        )

        assert loaded == "", f"importing rfc1902 pulled in pysmi: {loaded}"

    def test_import_does_not_load_requests_or_ssl(self):
        """The transitive network stack stays out too.

        ``requests`` and ``ssl`` are the expensive part of what pysmi drags in,
        and they are what a trap receiver most obviously has no use for. They
        are asserted separately from pysmi because a future pysmi could stop
        importing them, and that would make this pass for the right reason
        rather than silently stop testing anything.
        """
        loaded = _fresh_interpreter(
            """
            import sys
            import pysnmp.smi.rfc1902  # noqa: F401

            print(",".join(
                name for name in ("requests", "ssl") if name in sys.modules
            ))
            """
        )

        assert loaded == "", f"importing rfc1902 pulled in {loaded}"

    def test_compiler_still_reachable_from_its_own_module(self):
        """``addMibCompiler`` keeps its home in ``pysnmp.smi.compiler``.

        It was never in rfc1902's ``__all__``, so moving the import off the
        module namespace is not an API change -- but the function it moved
        away from must still be importable where it is documented to live.
        """
        from pysnmp.smi.compiler import addMibCompiler

        assert callable(addMibCompiler)


class TestResolutionUnchanged:
    """``resolveWithMib()`` behaves as it did before the import moved."""

    @pytest.fixture
    def mib_view_controller(self):
        return view.MibViewController(builder.MibBuilder())

    @pytest.fixture
    def recorded_calls(self, monkeypatch):
        """Capture ``addMibCompiler`` calls made during resolution."""
        calls = []

        def recorder(mibBuilder, **kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(rfc1902, "addMibCompiler", recorder, raising=False)
        monkeypatch.setattr(
            "pysnmp.smi.compiler.addMibCompiler", recorder, raising=False
        )

        return calls

    def test_resolution_still_works(self, mib_view_controller):
        """A MIB name resolves to the OID it always did."""
        identity = ObjectIdentity("SNMPv2-MIB", "sysDescr")
        identity.resolveWithMib(mib_view_controller)

        assert str(identity) == "1.3.6.1.2.1.1.1"

    def test_default_branch_passes_if_available_and_if_not_added(
        self, mib_view_controller, recorded_calls
    ):
        """With no ASN.1 sources configured, the compiler is attached softly.

        ``ifAvailable=True`` is what keeps a missing pysmi a no-op rather than
        an error, and ``ifNotAdded=True`` is what stops a second compiler being
        attached. Both are load-bearing for the default path.
        """
        identity = ObjectIdentity("SNMPv2-MIB", "sysDescr")
        identity.resolveWithMib(mib_view_controller)

        assert recorded_calls == [{"ifAvailable": True, "ifNotAdded": True}]

    def test_configured_sources_are_passed_through(
        self, mib_view_controller, recorded_calls
    ):
        """``addAsn1MibSource()`` forwards its sources and options verbatim."""
        identity = ObjectIdentity("SNMPv2-MIB", "sysDescr").addAsn1MibSource(
            "file:///tmp/mibs"
        )
        identity.resolveWithMib(mib_view_controller)

        assert len(recorded_calls) == 1
        assert recorded_calls[0]["sources"] == ("file:///tmp/mibs",)
