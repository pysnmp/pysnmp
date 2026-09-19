Codec benchmark
===============

How fast pysnmp encodes and decodes SNMP messages, how that is measured, and
what the measurement said the first time it was run.

Why there is one
----------------

In March 2017 a reporter polling thousands of devices moved the workload onto
pysnmp and found encode/decode was the bottleneck, measuring it at roughly six
times the cost of libsnmp (`etingof/pysnmp#44
<https://github.com/etingof/pysnmp/issues/44>`_). The report was never
answered. It was raised again here as `#290
<https://github.com/pysnmp/pysnmp/issues/290>`_, and the honest answer at the
time was that nobody could say whether it still described this fork: the
numbers were taken against pysnmp 4.x on Python 2 with a pyasn1 several majors
behind the current one, and there was no benchmark in the repository to ask.

``tools/benchmark_codec.py`` is that benchmark. It is a measuring instrument,
not a gate: it asserts no threshold, nothing fails when a number moves, and
what it produces is a table plus a statement of where the time went.

Running it
----------

.. code-block:: bash

   python tools/benchmark_codec.py                  # the table
   python tools/benchmark_codec.py --profile        # and where the time goes
   python tools/benchmark_codec.py --quick          # a fast sanity run
   python tools/benchmark_codec.py --json out.json --markdown out.md

The C baseline needs ``libnetsnmp``, which is ``libsnmp-dev`` on Debian and
Ubuntu and ``brew install net-snmp`` on macOS. Where it is not loadable the
benchmark says so in a note and reports the rest; ``--require-netsnmp`` turns
that into an error for a run that means to compare. ``PYSNMP_BENCH_NETSNMP_LIB``
names the library outright when it is somewhere the loader does not look, which
is the normal case for a keg-only Homebrew install.

In CI it is `Codec Benchmark
<https://github.com/pysnmp/pysnmp/actions/workflows/codec-benchmark.yml>`_,
which runs **on demand only** -- dispatched by hand against any branch, or by
labelling a pull request ``ci:benchmark``, which posts the combined table back
on the pull request. It is not on the push or pull-request path: the matrix
costs minutes of runner time and produces a measurement, not a verdict, so
there is nothing for a push to break. The matrix covers Linux, macOS and
Windows on the oldest and newest supported CPython, plus a free-threaded build
and PyPy.

What it measures
----------------

Three implementations, on the *same octets*:

``pysnmp``
    The real path: pyasn1's BER codec driven by the ``asn1Spec`` that
    ``pysnmp.proto.rfc1901`` and ``pysnmp.proto.rfc1905`` define. This is
    what an engine runs for every datagram.

``pyasn1``
    The same message declared from bare ``pyasn1.type.univ`` types -- same
    tags, same choices, same nesting, but none of pysnmp's subtype machinery:
    no value-range or size constraints, no named values, no
    ``pysnmp.proto.rfc1902`` subclasses. What separates this column from the
    one above is what pysnmp's own type layer costs; what is left is pyasn1's.

``netsnmp``
    ``libnetsnmp``'s ``snmp_pdu_parse`` and ``snmp_pdu_build`` through
    ``ctypes`` -- the modern stand-in for the reporter's libsnmp, and the floor
    a C implementation puts under the same work. The ``ctypes`` call overhead
    is counted against it, which is fair: it is what driving C from Python
    actually costs.

Two layers. The **PDU** body alone is the comparison, because all three
implementations do exactly that. The whole **message** -- version and community
included -- is pysnmp and pyasn1 only: net-snmp's message parse wants a
populated ``netsnmp_session`` and its own security processing, which is a
different amount of work and would not be the same measurement.

Three workloads, which is how the per-message and per-binding costs come apart:
one binding, ten (an interface row), and fifty (a GETBULK response). The values
cycle through the syntaxes a real poll returns -- counters, gauges, tick
counts, display strings, addresses, object identifiers -- so that no single
decoder path stands in for all of them.

Findings
--------

From run `35447776986
<https://github.com/pysnmp/pysnmp/actions/runs/35447776986>`_, the first with
every leg of the matrix reporting: CPython 3.14.7 on GitHub's ubuntu runner,
net-snmp 5.9.4, pysnmp 6.0.0-rc.15, pyasn1 2.0.3.

Read the ratios, not the microseconds. A shared runner is not a measuring
bench: the same ten-binding decode on the same leg read 429 us in the run
before this one and 622 us in this one, a 45% spread from nothing but the
machine, and the matrix's slowest platform is twice its fastest. What holds
steady across runs is the shape -- which column is bigger than which, and by
how much.

.. list-table:: PDU layer, microseconds per operation
   :header-rows: 1
   :widths: 20 12 12 12 12 16

   * - workload
     - bindings
     - pysnmp
     - pyasn1
     - netsnmp
     - pysnmp / netsnmp
   * - decode, single
     - 1
     - 110
     - 106
     - 2.0
     - 56x
   * - decode, poll
     - 10
     - 622
     - 590
     - 3.4
     - 186x
   * - decode, bulk
     - 50
     - 2839
     - 2750
     - 8.9
     - 321x
   * - encode, single
     - 1
     - 40
     - 39
     - 1.3
     - 31x
   * - encode, poll
     - 10
     - 209
     - 208
     - 1.9
     - 112x
   * - encode, bulk
     - 50
     - 940
     - 933
     - 4.4
     - 215x

**pysnmp's own type layer is not where the time is.** The bare-pyasn1 mirror of
the same message decodes within a couple of per cent of pysnmp's spec, and the
profile puts 0.4% of decode self time and none of encode in pysnmp's package.
The constraints, the named values and the ``pysnmp.proto.rfc1902``
subclasses -- the obvious suspects -- cost close to nothing at codec time.

**The codec is pyasn1**, which takes 84.8% of decode self time and 88.8% of
encode -- and 86.9% and 92.5% on PyPy, so this is not an artefact of one
interpreter. Of what remains, roughly a tenth is interpreter builtins (dictionary
updates, mostly) and 3-5% is ``logging.Logger.isEnabledFor``: pyasn1's debug
hooks ask whether debugging is on 577 times per ten-binding decode, and the
answer is always no.

**The cost is per binding, not per message.** Across the three workloads decode
fits ``54 us + 56 us per binding`` and encode ``21 us + 18 us per binding`` to
within a couple of per cent. Anything that would matter has to make a *binding*
cheaper; there is no per-message overhead worth attacking.

**Against a C codec the gap is two orders of magnitude, not six times.** That
is not the reporter's comparison restated -- what "libsnmp" named in 2017 is
ambiguous, and a ~6x ratio is what one would expect between two *Python*
implementations rather than against net-snmp's C library, which is what this
measures. Read the netsnmp column as the floor, and the pysnmp-versus-pyasn1
column as the only one that says anything about this repository's own code.

**The interpreter moves the number far more than anything in this repository
does.** The ten-binding decode, on one Linux runner, one run:

.. list-table::
   :header-rows: 1
   :widths: 40 20 20 20

   * - interpreter
     - decode (us)
     - encode (us)
     - vs 3.10
   * - CPython 3.10
     - 960
     - 383
     - --
   * - CPython 3.14
     - 622
     - 209
     - 1.5x
   * - CPython 3.14t (free-threaded)
     - 549
     - 212
     - 1.7x
   * - PyPy 3.11
     - 124
     - 34
     - 7.7x

**PyPy is where the answer to the original report is.** It decodes five times
faster than the newest CPython and eleven times faster than the oldest one this
package supports, and the free-threaded build is a little quicker than the
build with the GIL on a single thread. Nothing in this repository buys anything
close to that.

The PyPy line also needs its ``netsnmp`` column read carefully. That column
costs 8.5 to 14.5 us there against 2 to 3.4 us on CPython, for exactly the same
C calls: PyPy's ``ctypes`` bridge is the slow part, not ``libnetsnmp``. So the
gap narrowing to 12x on PyPy is pysnmp getting faster *and* the yardstick
getting slower, and the two cannot be separated with this instrument.

One more thing the matrix says and a single machine could not: on Windows the
3.10-to-3.14 comparison is much flatter than elsewhere -- 988 us against 911 us
-- where Linux and macOS both gain substantially.

**Running PyPy at all was the first thing this found.** Before the matrix
existed nobody had tried: ``import pysnmp.proto.rfc1902`` ended in a
``RecursionError`` there. ``pysnmp-pyasn1``'s ``NamedType`` subclasses a
:func:`~collections.namedtuple` and overrode ``__getitem__`` to return
``self.asn1Object``, and PyPy builds namedtuple field accessors out of
``__getitem__`` -- so the accessor called the override which called the
accessor. CPython's accessors read the tuple slot directly and never enter the
override, which is why the same code had always worked there and why five years
of CI had nothing to say about it.

Fixed in `pysnmp/pyasn1#185 <https://github.com/pysnmp/pyasn1/pull/185>`_ and
released as ``pysnmp-pyasn1`` 2.0.3, which is why the floor in
``pyproject.toml`` names that version: 2.0.2 is not importable on PyPy, and on
CPython the two are the same code. The leg is an ordinary part of the matrix
now.

One thing to know when reading it: PyPy measures a *warm* interpreter or it
measures the JIT. The harness sizes its own iteration counts and reports the
fastest of several samples, which gives the JIT somewhere to warm up, but a
short run -- ``--quick``, or a low ``--min-time`` -- reports compilation there
rather than the codec.

What it does not measure
------------------------

Codec only. No USM authentication or privacy, no MIB resolution, no transport,
no dispatcher -- a v3 exchange does all of those and they are not in these
numbers. The cProfile figures inflate every call they measure, so the split
between packages is what to read there, never the totals. And a CI runner is a
shared machine: each figure is the fastest of several samples for that reason,
and a difference of a few per cent between two runs is the runner, not the
code.
