Logging and tracing contract
============================

What these three packages may spend on observability, and where. It covers
pysnmp, pysmi and pyasn1, because the codec underneath is where the question
actually bites and a rule that stops at one repository's edge does not help.

It exists because the rule was unstated, and the default answer -- guard a
debug call with ``Logger.isEnabledFor()`` -- turns out to be correct advice
applied at a granularity that cannot afford it. Decoding one ten-binding
SNMPv2c response called ``isEnabledFor`` 551 times and got the same answer
every time, costing several per cent of the operation, paid by every install,
for output nobody had asked for (`pysnmp/pyasn1#187
<https://github.com/pysnmp/pyasn1/issues/187>`_).

.. contents::
   :local:
   :depth: 1


The rule
--------

**What an observability mechanism costs must be proportional to the
granularity of the thing it observes.**

That is the whole contract. Everything below is the arithmetic that makes it
concrete and the consequences that follow from it.

The reason it needs stating is that the cost is invisible at the call site.
``if LOG.isEnabledFor(logging.DEBUG):`` reads identically whether it sits in a
connection handler that runs once a minute or in a BER decoder that runs once
per ASN.1 component. The first is free. The second is a tax on everyone.


What things cost
----------------

Measured, not estimated. CPython 3.12, ``opentelemetry-sdk`` 1.44.0, best of
seven runs of 300,000 calls each.

.. list-table::
   :header-rows: 1
   :widths: 60 20

   * - per call
     - cost
   * - module-global flag, ``if _DEBUG:``
     - 7 ns
   * - ``held_span.is_recording()``
     - 20 ns
   * - ``Logger.isEnabledFor(DEBUG)``
     - 41 ns
   * - ``logger.debug("x")``, unguarded
     - 77 ns
   * - ``logger.debug("x %s", v)``, unguarded
     - 91 ns
   * - ``trace.get_current_span()`` -- a contextvar lookup
     - 220 ns
   * - ``get_current_span().is_recording()``
     - 240 ns
   * - ``span.add_event("e")``
     - 1,212 ns
   * - ``span.add_event("e", {...})``
     - ~2,600 ns
   * - ``start_as_current_span()``, API only, no SDK
     - 3,038 ns
   * - ``start_as_current_span()``, SDK, ``ALWAYS_OFF``
     - 5,251 ns
   * - ``start_as_current_span()``, SDK, ``ALWAYS_ON``
     - 9,426 ns

Three of those are worth reading twice.

**A span costs 5 µs even when the sampler says no.** ``ALWAYS_OFF`` is more
expensive than the no-op tracer, because an SDK span is constructed before a
sampler is consulted. "We will sample it away in production" does not rescue a
span that should not have been started.

**The no-op tracer is not free.** With no SDK installed at all,
``start_as_current_span()`` still costs 3 µs. An optional telemetry extra that
"degrades gracefully when unconfigured" degrades to *correct*, not to *costless*.

**OpenTelemetry's gate is cheaper than the standard library's** --
``is_recording()`` on a span you already hold is 20 ns against
``isEnabledFor``'s 41 ns. What is expensive is *finding* the span:
``get_current_span()`` is 220 ns because it walks a contextvar. So an OTel
guard is affordable exactly when the span is in hand, and never inside a loop
that has to look it up.


The budget, by granularity
--------------------------

Against a ten-binding SNMPv2c response: ~575 µs to decode, ~200 µs to encode,
551 guard sites hit on the decode, 10 varbinds, one network round trip
measured in milliseconds.

.. list-table::
   :header-rows: 1
   :widths: 34 22 22 22

   * - mechanism
     - per exchange
     - per varbind
     - per ASN.1 component
   * - module flag / per-operation refresh
     - free
     - free
     - free
   * - ``Logger.isEnabledFor``
     - free
     - 0.1%
     - 4-6%
   * - ``span.add_event(...)``
     - free
     - 2%
     - **+122%**
   * - a span each
     - <1%
     - 9%
     - **5x the whole decode**

Which gives the line this contract is really about:

**Nothing below the PDU boundary may reach a production telemetry pipeline.**

Not as a matter of taste. A span per component is five times the cost of the
work it describes.


Two audiences, two mechanisms
-----------------------------

Most of the trouble comes from one mechanism trying to serve both.

Developer diagnostics
~~~~~~~~~~~~~~~~~~~~~

Somebody is debugging a malformed PDU or a codec defect. They want every tag,
every length, every component, and hexdumps. It is rare, interactive, local,
and it happens on one message rather than a million.

* **Enabled through the standard library.** ``logging.getLogger("pysnmp")`` and
  ``logging.getLogger("pyasn1")``, level set with
  :meth:`logging.Logger.setLevel`. It composes with whatever configuration the
  host already has, and it is what people already know. No bespoke switch.
* **The check is hoisted out of the hot path.** Per operation, never per
  component. Where a re-entrancy hook already exists, use it -- pyasn1's
  ``Decoder.__call__`` tracks nesting depth for ``MAX_NESTING_DEPTH``, so
  depth zero is exactly "a decode is starting". Where one does not exist,
  create it structurally rather than by threading state through the recursion;
  see the cautionary tale below.
* **Refresh, do not cache at import.** A flag evaluated once at import is
  faster still and silently ignores the ``setLevel()`` call this contract just
  told people to make. Re-reading per operation costs one check per operation
  and keeps the documented path working.
* **Never pay per component when off.** If a future floor of Python 3.12
  arrives, :mod:`sys.monitoring` (:pep:`669`) is the only mechanism that is
  genuinely zero when no tool is registered, rather than merely cheap.

One consequence worth naming: because :class:`logging.LogRecord` construction
calls ``findCaller()``, which walks the stack per record, a codec emitting
hundreds of records per message is not usable with debugging on. **The
capability cannot be exercised in production, so it must not be charged for in
production.** That asymmetry, rather than the raw percentage, is the argument.

Operational observability
~~~~~~~~~~~~~~~~~~~~~~~~~

Somebody is running a poller and wants to know what it is doing. This is
pysnmp's concern and never pyasn1's or pysmi's.

* **Spans at the SNMP exchange boundary.** One per request/response, carrying
  version, PDU type, varbind count, retries, error-status. At ~9 µs against a
  round trip in milliseconds this is under 1%.
* **Metrics, not events, for anything that is a rate or a distribution.**
  Operation counts, security-model counts, ``errind`` counts and latency
  histograms are all aggregates. A counter increment is cheaper than an event
  and does not invite a cardinality argument.
* **Events only for the rare and the diagnostic** -- a decode failure, a
  constraint violation, an unresolved arc. Never for the ordinary case.
* **Hold the span.** Never call ``get_current_span()`` inside a loop.
* **Attribute cardinality is bounded by construction.** Record module
  identity, counts, types and error codes -- never resolved OIDs, addresses,
  community strings or varbind values. `#294
  <https://github.com/pysnmp/pysnmp/issues/294>`_ sets this out in detail; the
  discipline there applies unchanged to span and metric attributes.

Operational logging
~~~~~~~~~~~~~~~~~~~

Ordinary :mod:`logging` at ``WARNING`` and above, at the engine boundary, for
things an operator should see without enabling anything: authentication
failures, timeouts, unknown engine IDs. Cheap because it is rare.


Rules for library code
----------------------

These apply to all three packages.

**Never configure logging.** Attach :class:`logging.NullHandler` and leave
levels, handlers and formatters to the application.

**Never set a telemetry provider.** Call ``trace.get_tracer(__name__)`` and
nothing else. ``trace.set_tracer_provider()`` is process-global and warns and
no-ops on a second call, so a library that sets it either loses to the host or
beats the host to it. This is the same hazard as OpenFeature's
``set_provider()`` without a domain, analysed in `#294
<https://github.com/pysnmp/pysnmp/issues/294>`_.

**Depend on the API, never the SDK.** ``opentelemetry-api`` may be a
dependency of an optional extra; ``opentelemetry-sdk`` is the application's
choice.

**Keep interpolation lazy.** ``logger.debug("x=%s", v)``, never
``logger.debug(f"x={v}")`` -- an f-string formats whether or not anything will
print it. All three repositories select ruff's ``G`` rules
(``flake8-logging-format``), which enforces this; leave them selected.

**Guard argument construction, not the call.** The guard exists so the
``extra`` dict and the hexdump are not built. That is a real saving and worth
keeping. What must not happen is evaluating the guard itself per component.


A cautionary tale
-----------------

The obvious fix is not uniformly safe, which is the main reason this page
exists rather than a one-line style rule.

pyasn1's decoder took the per-operation refresh cleanly: ``Decoder.__call__``
already threads ``_nestingLevel``, so the flag is re-read at depth zero and
551 checks became 1 (`pysnmp/pyasn1#188
<https://github.com/pysnmp/pyasn1/pull/188>`_).

The encoder has 337 checks and no such marker. Adding one the same way -- a
private key threaded through its ``**options`` chain -- **measured 13% slower,
reproducibly**, because the key then rides through roughly 65 nested
``**options`` expansions per encode. That costs more than the 337 calls it
saves. Removing the marker again made encode faster in six of six paired
rounds.

So: measure the fix, not just the problem. The rule at the top of this page
says where instrumentation may live; it does not promise that any particular
way of getting it there is free.


How to measure a change here
----------------------------

Two instruments, and the cheap one is the trustworthy one.

**Count the calls.** Wrapping ``logging.Logger.isEnabledFor`` and running one
operation gives an exact, noise-free number -- 551 before, 1 after. Multiply
by the per-call cost above for an analytic prediction. This is deterministic
and reproducible on any machine.

**Then time it, paired.** Two trees selected by ``PYTHONPATH``, alternating
between them, a dozen rounds, comparing each round against its neighbour.
Report the paired median and how many pairs the change won. Absolute figures
drift: the same decode read 575 µs before a host restart and ~400 µs after,
and per-variant standard deviation ran near 10% -- larger than a 4% effect.

**Do not trust a profiler's line attribution on its own.** Sampled profiles
over-credit small, very frequently called functions, in the same way
``cProfile``'s per-call overhead does. Chasing one such attribution in
``Asn1Type.__init__`` produced a change that measured 574.26 µs against
574.98 µs -- nothing at all. Treat a profile as a ranking of where to look,
never as a budget of what is available.

``tools/benchmark_codec.py`` builds the workloads used throughout; see
:doc:`codec-benchmark`.
