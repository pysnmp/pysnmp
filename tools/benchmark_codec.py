#!/usr/bin/env python
"""BER encode and decode throughput for a representative SNMPv2c exchange.

Why this exists
---------------

`#290 <https://github.com/pysnmp/pysnmp/issues/290>`_ carries a nine-year-old
upstream report (`etingof/pysnmp#44
<https://github.com/etingof/pysnmp/issues/44>`_) that pysnmp decoded SNMPv2c
about six times slower than libsnmp. Those numbers were taken against pysnmp
4.x on Python 2 with a pyasn1 several majors behind this one, and nobody could
say whether they still described this fork, because there was no benchmark to
ask. This is that benchmark.

It is a measuring instrument, not a gate. Nothing here asserts a threshold: it
prints numbers, writes them as JSON, and says where the time went. What any of
it justifies is separate work.

What it measures
----------------

Three implementations decode and encode the *same octets*:

``pysnmp``
    The real path -- ``pyasn1``'s BER codec driven by the ``asn1Spec`` that
    ``pysnmp.proto.rfc1901`` and ``rfc1905`` define. This is what an engine
    runs for every datagram.

``pyasn1``
    The same message structure declared from bare ``pyasn1.type.univ`` types
    -- same tags, same choices, same nesting, but none of pysnmp's subtype
    machinery: no value-range or size constraints, no named values, no
    ``rfc1902`` subclasses. The gap between this and ``pysnmp`` is what
    pysnmp's own type layer costs on top of the codec; whatever is left is
    pyasn1's.

``netsnmp``
    ``libnetsnmp``'s ``snmp_pdu_parse`` and ``snmp_pdu_build`` called through
    ``ctypes`` -- the modern stand-in for the reporter's libsnmp, and the floor
    a C implementation puts under the same work. Optional: skipped, with a
    note, wherever the shared library is not loadable. The ``ctypes`` call
    overhead is counted against it, which flatters nobody: it is a real cost
    of driving C from Python.

Two layers, because only one of them compares:

``pdu``
    The PDU body alone -- the tagged ``ResponsePDU`` and its variable
    bindings. All three implementations do this, so this is the comparison.

``message``
    The whole SNMPv2c message, version and community included. pysnmp and
    pyasn1 only: net-snmp's message parse wants a populated ``netsnmp_session``
    and its own security processing, which is a different amount of work and
    would not be the same measurement.

Usage
-----

::

    python tools/benchmark_codec.py                     # the table
    python tools/benchmark_codec.py --quick             # fewer samples
    python tools/benchmark_codec.py --profile           # where the time goes
    python tools/benchmark_codec.py --json results.json --markdown summary.md

``.github/workflows/codec-benchmark.yml`` runs it on demand across the
platform and interpreter matrix. ``tests/test_benchmark_codec.py`` holds the
harness itself honest -- that the workloads round-trip, that the bare-pyasn1
mirror decodes the pysnmp octets to the same values, and that the reported
shape is what the workflow reads.
"""

import argparse
import collections
import cProfile
import ctypes
import ctypes.util
import json
import os
import platform
import pstats
import statistics
import sys
import sysconfig
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import pyasn1
from pyasn1.codec.ber import decoder, encoder
from pyasn1.type import namedtype, tag, univ

import pysnmp
from pysnmp.proto import rfc1901, rfc1902, rfc1905
from pysnmp.proto.api import v2c

# ---------------------------------------------------------------------------
# The message structure, declared a second time from bare pyasn1
# ---------------------------------------------------------------------------
#
# A mirror of what pysnmp.proto.rfc1902 and rfc1905 declare: same tags, same
# alternatives in the same order, same nesting. What it leaves out is
# everything pysnmp adds on top of pyasn1 -- the ValueRangeConstraint on every
# integer, the ValueSizeConstraint on every string, errorStatus's nineteen
# named values, and the rfc1902 subclasses themselves with their overridden
# constructors.
#
# Both specs therefore ask the decoder for the same structural work, and the
# difference between them is pysnmp's type layer rather than a different
# amount of parsing. Keeping the full eight-alternative PDUs choice is part of
# that: dispatching a response through it is what the protocol costs, not what
# pysnmp costs, so the mirror pays it too.


def _application(number: int, base: Any) -> Any:
    """Tag a universal type into the APPLICATION class, the way SMIv2 does."""
    return base.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatSimple, number)
    )


def _context(number: int, base: Any, constructed: bool = False) -> Any:
    """Tag a universal type into the CONTEXT class, the way RFC 1905 does."""
    return base.tagSet.tagImplicitly(
        tag.Tag(
            tag.tagClassContext,
            tag.tagFormatConstructed if constructed else tag.tagFormatSimple,
            number,
        )
    )


class BareIpAddress(univ.OctetString):
    """``IpAddress`` with no four-octet size constraint."""

    tagSet = _application(0x00, univ.OctetString)


class BareCounter32(univ.Integer):
    """``Counter32`` with no 0..4294967295 range constraint."""

    tagSet = _application(0x01, univ.Integer)


class BareGauge32(univ.Integer):
    """``Gauge32`` with no range constraint."""

    tagSet = _application(0x02, univ.Integer)


class BareTimeTicks(univ.Integer):
    """``TimeTicks`` with no range constraint."""

    tagSet = _application(0x03, univ.Integer)


class BareOpaque(univ.OctetString):
    """``Opaque`` with none of rfc1902's float and double unwrapping."""

    tagSet = _application(0x04, univ.OctetString)


class BareCounter64(univ.Integer):
    """``Counter64`` with no 0..18446744073709551615 range constraint."""

    tagSet = _application(0x06, univ.Integer)


class BareSimpleSyntax(univ.Choice):
    """RFC 1902 ``SimpleSyntax``, from universal types only."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("integer-value", univ.Integer()),
        namedtype.NamedType("string-value", univ.OctetString()),
        namedtype.NamedType("objectID-value", univ.ObjectIdentifier()),
    )


class BareApplicationSyntax(univ.Choice):
    """RFC 1902 ``ApplicationSyntax``, from the bare application types above."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("ipAddress-value", BareIpAddress()),
        namedtype.NamedType("counter-value", BareCounter32()),
        namedtype.NamedType("timeticks-value", BareTimeTicks()),
        namedtype.NamedType("arbitrary-value", BareOpaque()),
        namedtype.NamedType("big-counter-value", BareCounter64()),
        namedtype.NamedType("gauge32-value", BareGauge32()),
    )


class BareObjectSyntax(univ.Choice):
    """RFC 1902 ``ObjectSyntax``."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("simple", BareSimpleSyntax()),
        namedtype.NamedType("application-wide", BareApplicationSyntax()),
    )


class BareNoSuchObject(univ.Null):
    """RFC 1905 ``noSuchObject``."""

    tagSet = _context(0x00, univ.Null)


class BareNoSuchInstance(univ.Null):
    """RFC 1905 ``noSuchInstance``."""

    tagSet = _context(0x01, univ.Null)


class BareEndOfMibView(univ.Null):
    """RFC 1905 ``endOfMibView``."""

    tagSet = _context(0x02, univ.Null)


class BareBindValue(univ.Choice):
    """The value half of a variable binding, exception markers included."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("value", BareObjectSyntax()),
        namedtype.NamedType("unSpecified", univ.Null("")),
        namedtype.NamedType("noSuchObject", BareNoSuchObject("")),
        namedtype.NamedType("noSuchInstance", BareNoSuchInstance("")),
        namedtype.NamedType("endOfMibView", BareEndOfMibView("")),
    )


class BareVarBind(univ.Sequence):
    """RFC 1905 ``VarBind``."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("name", univ.ObjectIdentifier()),
        namedtype.NamedType("", BareBindValue()),
    )


class BareVarBindList(univ.SequenceOf):
    """RFC 1905 ``VarBindList``, without the 0..max-bindings size constraint."""

    componentType = BareVarBind()


class BarePDU(univ.Sequence):
    """RFC 1905 ``PDU``, without errorStatus's named values."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("request-id", univ.Integer()),
        namedtype.NamedType("error-status", univ.Integer()),
        namedtype.NamedType("error-index", univ.Integer()),
        namedtype.NamedType("variable-bindings", BareVarBindList()),
    )


class BareBulkPDU(univ.Sequence):
    """RFC 1905 ``BulkPDU``."""

    tagSet = _context(5, univ.Sequence, constructed=True)
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("request-id", univ.Integer()),
        namedtype.NamedType("non-repeaters", univ.Integer()),
        namedtype.NamedType("max-repetitions", univ.Integer()),
        namedtype.NamedType("variable-bindings", BareVarBindList()),
    )


def _bare_pdu(number: int) -> Any:
    """One context-tagged alternative of the PDUs choice."""

    class _Tagged(BarePDU):
        tagSet = _context(number, univ.Sequence, constructed=True)

    return _Tagged()


class BarePDUs(univ.Choice):
    """RFC 1905 ``PDUs`` -- all eight alternatives, as the real spec has them."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("get-request", _bare_pdu(0)),
        namedtype.NamedType("get-next-request", _bare_pdu(1)),
        namedtype.NamedType("get-bulk-request", BareBulkPDU()),
        namedtype.NamedType("response", _bare_pdu(2)),
        namedtype.NamedType("set-request", _bare_pdu(3)),
        namedtype.NamedType("inform-request", _bare_pdu(6)),
        namedtype.NamedType("snmpV2-trap", _bare_pdu(7)),
        namedtype.NamedType("report", _bare_pdu(8)),
    )


class BareMessage(univ.Sequence):
    """RFC 1901 ``Message``, without version's named values."""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType("version", univ.Integer()),
        namedtype.NamedType("community", univ.OctetString()),
        namedtype.NamedType("data", BarePDUs()),
    )


# ---------------------------------------------------------------------------
# Workloads
# ---------------------------------------------------------------------------


@dataclass
class Workload:
    """One SNMPv2c response, held as both objects and octets.

    Attributes
    ----------
    name:
        What the results call it.
    description:
        What it stands for, for the table header.
    varbinds:
        How many variable bindings it carries, which is what the per-binding
        figures divide by.
    message:
        The pysnmp ``rfc1901.Message`` object, ready to encode.
    pdu:
        The ``ResponsePDU`` inside it, ready to encode on its own.
    message_octets:
        The encoded message, ready to decode.
    pdu_octets:
        The encoded PDU body, ready to decode -- and what net-snmp parses.
    """

    name: str
    description: str
    varbinds: int
    message: Any
    pdu: Any
    message_octets: bytes
    pdu_octets: bytes


def _values_for(index: int) -> Any:
    """A value for binding *index*, cycling through the syntaxes a poll returns.

    A real response is not a column of identical counters: interface tables
    mix counters, gauges, tick counts, display strings and addresses, and each
    of those is a different decoder path. Cycling through them keeps one
    syntax from dominating the measurement.
    """
    syntaxes = (
        lambda: rfc1902.Counter32(1234567 * index % 4294967295),
        lambda: rfc1902.OctetString(f"GigabitEthernet0/{index}"),
        lambda: rfc1902.Counter64(9876543210 * index % 18446744073709551615),
        lambda: rfc1902.Gauge32(1000000000),
        lambda: rfc1902.TimeTicks(31415926 + index),
        lambda: rfc1902.Integer32(index % 2 + 1),
        lambda: rfc1902.IpAddress(f"10.0.{index % 256}.1"),
        lambda: rfc1902.ObjectIdentifier((1, 3, 6, 1, 4, 1, 9, 1, index)),
    )
    return syntaxes[index % len(syntaxes)]()


def build_workload(name: str, description: str, varbinds: int) -> Workload:
    """Build one response of *varbinds* bindings and encode it both ways."""
    pdu = v2c.GetResponsePDU()
    v2c.apiPDU.setDefaults(pdu)
    v2c.apiPDU.setRequestID(pdu, 0x7E57)
    v2c.apiPDU.setErrorStatus(pdu, 0)
    v2c.apiPDU.setErrorIndex(pdu, 0)
    v2c.apiPDU.setVarBinds(
        pdu,
        [
            ((1, 3, 6, 1, 2, 1, 2, 2, 1, 1 + (i % 22), 1 + i), _values_for(i))
            for i in range(varbinds)
        ],
    )

    message = rfc1901.Message()
    v2c.apiMessage.setDefaults(message)
    v2c.apiMessage.setCommunity(message, "public")
    v2c.apiMessage.setPDU(message, pdu)

    return Workload(
        name=name,
        description=description,
        varbinds=varbinds,
        message=message,
        pdu=pdu,
        message_octets=encoder.encode(message),
        pdu_octets=encoder.encode(pdu),
    )


#: The three shapes worth separating. One binding is the per-message floor --
#: everything that happens whether or not there is data in the message. Ten is
#: an ordinary poll of one interface row. Fifty is what a GETBULK walk hands
#: back, and it is the shape a poller at scale spends its day on. Comparing
#: the three says how much of the cost is per message and how much is per
#: binding, which decides what an optimisation could even aim at.
WORKLOADS = (
    ("single", "one binding -- the per-message floor", 1),
    ("poll", "ten bindings -- one interface row", 10),
    ("bulk", "fifty bindings -- a GETBULK response", 50),
)


def build_workloads(names: list[str] | None = None) -> list[Workload]:
    """Build every workload, or only the named ones."""
    wanted = set(names or [])
    return [
        build_workload(name, description, varbinds)
        for name, description, varbinds in WORKLOADS
        if not wanted or name in wanted
    ]


# ---------------------------------------------------------------------------
# The net-snmp baseline, through ctypes
# ---------------------------------------------------------------------------


class NetSnmpUnavailable(Exception):
    """Raised when libnetsnmp cannot be loaded or does not behave as expected."""


#: Where to look for the shared library, in order. ``find_library`` covers the
#: usual Linux and macOS installs; the explicit sonames cover a Debian or
#: Ubuntu box where the ``-dev`` package (and so the bare ``.so`` symlink) is
#: not installed, which is the normal state of a CI runner.
_NETSNMP_CANDIDATES = (
    "libnetsnmp.so.40",
    "libnetsnmp.so.35",
    "libnetsnmp.so",
    "libnetsnmp.dylib",
    "libnetsnmp.40.dylib",
)

#: SNMPv2c response PDU, the command snmp_pdu_create() is asked for. The tag
#: in the octets decides what snmp_pdu_parse() actually fills in; this only
#: has to be a PDU type net-snmp will allocate.
_SNMP_MSG_RESPONSE = 0xA2

#: Room for a rebuilt PDU. net-snmp emits long-form lengths where pyasn1 emits
#: minimal ones, so its output is a little larger than the input -- a few
#: octets per constructed element, nowhere near this.
_BUILD_BUFFER = 65536


class NetSnmpCodec:
    """libnetsnmp's BER codec, reached through ctypes.

    Only three entry points are needed and none of them require reaching into
    ``netsnmp_pdu``: the PDU is allocated, filled and freed by the library and
    is never anything but an opaque pointer here. That matters, because the
    struct's layout is a compile-time detail that changes between net-snmp
    releases and guessing at it from Python is how a benchmark quietly starts
    measuring a segfault.
    """

    def __init__(self, path: str | None = None) -> None:
        """Load the library and bind the three functions the benchmark calls."""
        self.path = path or self._find()
        if not self.path:
            raise NetSnmpUnavailable("libnetsnmp was not found on this system")

        try:
            self.lib = ctypes.CDLL(self.path)
        except OSError as exc:
            raise NetSnmpUnavailable(f"{self.path} could not be loaded: {exc}") from exc

        try:
            self.lib.snmp_pdu_create.restype = ctypes.c_void_p
            self.lib.snmp_pdu_create.argtypes = [ctypes.c_int]
            # net-snmp 5.8 changed snmp_pdu_parse's return from a pointer into
            # the substrate to an int status, so neither the value nor its
            # width is a reliable success signal across the versions a runner
            # might have. Success is established by _self_check() instead,
            # which reads the parse back out through snmp_pdu_build().
            self.lib.snmp_pdu_parse.restype = ctypes.c_int
            self.lib.snmp_pdu_parse.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self.lib.snmp_pdu_build.restype = ctypes.POINTER(ctypes.c_ubyte)
            self.lib.snmp_pdu_build.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self.lib.snmp_free_pdu.restype = None
            self.lib.snmp_free_pdu.argtypes = [ctypes.c_void_p]
        except AttributeError as exc:
            raise NetSnmpUnavailable(
                f"{self.path} does not export the BER codec: {exc}"
            ) from exc

        self.version = self._version()

    @staticmethod
    def _find() -> str | None:
        """The library's path, from the environment or the usual places."""
        override = os.environ.get("PYSNMP_BENCH_NETSNMP_LIB")
        if override:
            return override

        found = ctypes.util.find_library("netsnmp")
        if found:
            return found

        for candidate in _NETSNMP_CANDIDATES:
            try:
                ctypes.CDLL(candidate)
            except OSError:
                continue
            return candidate

        return None

    def _version(self) -> str | None:
        """What ``netsnmp_get_version()`` says, when the symbol is there."""
        try:
            getter = self.lib.netsnmp_get_version
        except AttributeError:
            return None
        getter.restype = ctypes.c_char_p
        getter.argtypes = []
        value = getter()
        return value.decode("ascii", "replace") if value else None

    def decode(self, buffer: Any, length: int) -> None:
        """Parse a PDU body and free it again -- one unit of decode work."""
        pdu = self.lib.snmp_pdu_create(_SNMP_MSG_RESPONSE)
        remaining = ctypes.c_size_t(length)
        self.lib.snmp_pdu_parse(pdu, buffer, ctypes.byref(remaining))
        self.lib.snmp_free_pdu(pdu)

    def parse(self, octets: bytes) -> Any:
        """A parsed PDU handle, for the encode benchmark to build from."""
        buffer = (ctypes.c_ubyte * len(octets)).from_buffer_copy(octets)
        pdu = self.lib.snmp_pdu_create(_SNMP_MSG_RESPONSE)
        remaining = ctypes.c_size_t(len(octets))
        self.lib.snmp_pdu_parse(pdu, buffer, ctypes.byref(remaining))
        if remaining.value:
            self.lib.snmp_free_pdu(pdu)
            raise NetSnmpUnavailable(
                f"snmp_pdu_parse() left {remaining.value} octets unread"
            )
        return pdu

    def encode(self, pdu: Any, buffer: Any) -> int:
        """Build a PDU body from a parsed PDU -- one unit of encode work."""
        remaining = ctypes.c_size_t(_BUILD_BUFFER)
        result = self.lib.snmp_pdu_build(pdu, buffer, ctypes.byref(remaining))
        if not result:
            raise NetSnmpUnavailable("snmp_pdu_build() failed")
        return _BUILD_BUFFER - remaining.value

    def free(self, pdu: Any) -> None:
        """Release a PDU obtained from :meth:`parse`."""
        self.lib.snmp_free_pdu(pdu)

    def self_check(self, workload: Workload) -> None:
        """Prove the binding works before anything it produces is reported.

        Parse the workload, build it back out and decode *that* with pysnmp:
        if the bindings survive the round trip through C, the library is doing
        the job the benchmark is about to time it on. Comparing octets would
        not do -- net-snmp writes long-form lengths where pyasn1 writes
        minimal ones, so the two encodings of the same PDU differ by a few
        bytes and both are valid BER.
        """
        pdu = self.parse(workload.pdu_octets)
        try:
            buffer = (ctypes.c_ubyte * _BUILD_BUFFER)()
            written = self.encode(pdu, buffer)
            rebuilt = bytes(buffer[:written])
        finally:
            self.free(pdu)

        decoded, trailing = decoder.decode(rebuilt, asn1Spec=rfc1905.PDUs())
        if trailing:
            raise NetSnmpUnavailable("snmp_pdu_build() output had trailing octets")

        original = v2c.apiPDU.getVarBinds(workload.pdu)
        produced = v2c.apiPDU.getVarBinds(decoded.getComponent())
        if len(original) != len(produced):
            raise NetSnmpUnavailable(
                f"round trip changed the binding count: "
                f"{len(original)} in, {len(produced)} out"
            )
        for (name, value), (name2, value2) in zip(original, produced):
            if name != name2 or value != value2:
                raise NetSnmpUnavailable(
                    f"round trip changed a binding: {name}={value!r} "
                    f"became {name2}={value2!r}"
                )


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


@dataclass
class Measurement:
    """What one case measured, and enough context to read it later."""

    workload: str
    layer: str
    direction: str
    implementation: str
    varbinds: int
    octets: int
    iterations: int
    repeats: int
    usec_per_op: float
    usec_per_op_median: float
    ops_per_sec: float
    usec_per_varbind: float
    samples: list[float] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str, str]:
        """What identifies the row this belongs in: workload, layer, direction."""
        return (self.workload, self.layer, self.direction)


def _autorange(operation: Callable[[], Any], min_time: float) -> int:
    """How many iterations it takes for one sample to last *min_time*.

    The same escalation ``timeit.Timer.autorange`` uses. A fixed iteration
    count cannot serve both a one-binding decode and a fifty-binding one, and
    a sample shorter than the clock's resolution measures the clock.
    """
    iterations = 1
    while True:
        start = time.perf_counter()
        for _ in range(iterations):
            operation()
        elapsed = time.perf_counter() - start
        if elapsed >= min_time:
            return iterations
        if iterations >= 1 << 30:
            return iterations
        iterations *= 10 if elapsed < min_time / 10 else 2


def measure(
    operation: Callable[[], Any],
    min_time: float,
    repeats: int,
) -> tuple[int, list[float]]:
    """Time *operation*, returning the iteration count and one figure per repeat.

    Each repeat is reported rather than averaged into the others. A CI runner
    is a shared machine and its noise is one-sided -- something else stealing
    the core makes a sample slower, never faster -- so the minimum is the
    figure that says most about the code, and the spread across repeats is
    what says whether to believe it.
    """
    operation()  # Warm up: first call imports, allocates and fills caches.
    iterations = _autorange(operation, min_time)

    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(iterations):
            operation()
        samples.append((time.perf_counter() - start) / iterations * 1e6)

    return iterations, samples


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def _pysnmp_cases(workload: Workload) -> list[tuple[str, str, str, Callable[[], Any]]]:
    """The real path: pyasn1's codec driven by pysnmp's own spec objects."""
    message_spec = rfc1901.Message()
    pdu_spec = rfc1905.PDUs()
    message_octets = workload.message_octets
    pdu_octets = workload.pdu_octets
    message = workload.message
    pdu = workload.pdu

    return [
        (
            "message",
            "decode",
            "pysnmp",
            lambda: decoder.decode(message_octets, asn1Spec=message_spec),
        ),
        ("message", "encode", "pysnmp", lambda: encoder.encode(message)),
        (
            "pdu",
            "decode",
            "pysnmp",
            lambda: decoder.decode(pdu_octets, asn1Spec=pdu_spec),
        ),
        ("pdu", "encode", "pysnmp", lambda: encoder.encode(pdu)),
    ]


def _pyasn1_cases(workload: Workload) -> list[tuple[str, str, str, Callable[[], Any]]]:
    """The same octets against the bare-pyasn1 mirror of the same structure."""
    message_spec = BareMessage()
    pdu_spec = BarePDUs()
    message_octets = workload.message_octets
    pdu_octets = workload.pdu_octets

    # Encoding needs an object, and it has to be one the mirror produced:
    # handing the encoder a pysnmp object would measure the pysnmp types again
    # under a pyasn1 label.
    message_object, _ = decoder.decode(message_octets, asn1Spec=message_spec)
    pdu_object, _ = decoder.decode(pdu_octets, asn1Spec=pdu_spec)

    return [
        (
            "message",
            "decode",
            "pyasn1",
            lambda: decoder.decode(message_octets, asn1Spec=message_spec),
        ),
        ("message", "encode", "pyasn1", lambda: encoder.encode(message_object)),
        (
            "pdu",
            "decode",
            "pyasn1",
            lambda: decoder.decode(pdu_octets, asn1Spec=pdu_spec),
        ),
        ("pdu", "encode", "pyasn1", lambda: encoder.encode(pdu_object)),
    ]


def _netsnmp_cases(
    workload: Workload, codec: NetSnmpCodec
) -> list[tuple[str, str, str, Callable[[], Any]]]:
    """Libnetsnmp on the PDU body -- the only layer that compares."""
    octets = workload.pdu_octets
    substrate = (ctypes.c_ubyte * len(octets)).from_buffer_copy(octets)
    length = len(octets)

    # One parsed PDU, reused for every encode iteration. pysnmp's encode case
    # reuses one object too, so neither side is charged for building the thing
    # it is about to serialise.
    parsed = codec.parse(octets)
    out = (ctypes.c_ubyte * _BUILD_BUFFER)()

    return [
        ("pdu", "decode", "netsnmp", lambda: codec.decode(substrate, length)),
        ("pdu", "encode", "netsnmp", lambda: codec.encode(parsed, out)),
    ]


def run_benchmark(
    workloads: list[Workload],
    codec: NetSnmpCodec | None,
    min_time: float,
    repeats: int,
    verbose: bool = True,
) -> list[Measurement]:
    """Run every case of every workload and collect the measurements."""
    measurements = []

    for workload in workloads:
        cases = _pysnmp_cases(workload) + _pyasn1_cases(workload)
        if codec is not None:
            cases += _netsnmp_cases(workload, codec)

        for layer, direction, implementation, operation in cases:
            if verbose:
                print(
                    f"  {workload.name}/{layer}/{direction}/{implementation} ...",
                    end="",
                    flush=True,
                    file=sys.stderr,
                )
            iterations, samples = measure(operation, min_time, repeats)
            best = min(samples)
            octets = (
                len(workload.message_octets)
                if layer == "message"
                else len(workload.pdu_octets)
            )
            measurements.append(
                Measurement(
                    workload=workload.name,
                    layer=layer,
                    direction=direction,
                    implementation=implementation,
                    varbinds=workload.varbinds,
                    octets=octets,
                    iterations=iterations,
                    repeats=repeats,
                    usec_per_op=best,
                    usec_per_op_median=statistics.median(samples),
                    ops_per_sec=1e6 / best,
                    usec_per_varbind=best / workload.varbinds,
                    samples=samples,
                )
            )
            if verbose:
                print(f" {best:.2f} us", file=sys.stderr)

    return measurements


# ---------------------------------------------------------------------------
# Where the time goes
# ---------------------------------------------------------------------------

#: How a profiled frame's file is attributed.
_ATTRIBUTION = ("pysnmp", "pyasn1", "stdlib", "builtins", "benchmark")


def _normalise(path: str) -> str:
    """A path in one spelling, so a prefix test means the same on every platform."""
    return os.path.normcase(os.path.abspath(path)).replace("\\", "/")


#: Where each package actually lives, taken from the imported module rather
#: than matched on name. A checkout of this repository is itself a directory
#: called ``pysnmp``, and pyasn1 installed under it has ``/pysnmp/`` in its
#: path -- so matching on the name alone files most of pyasn1's decoder under
#: pysnmp and inverts the answer this is here to give.
_PACKAGE_ROOTS = (
    ("pysnmp", _normalise(os.path.dirname(pysnmp.__file__))),
    ("pyasn1", _normalise(os.path.dirname(pyasn1.__file__))),
    ("benchmark", _normalise(__file__)),
)


def _attribute(filename: str) -> str:
    """Which of :data:`_ATTRIBUTION` a profiled frame's file belongs to."""
    if filename == "~":
        return "builtins"

    normalised = _normalise(filename)
    for name, root in _PACKAGE_ROOTS:
        if normalised == root or normalised.startswith(root + "/"):
            return name

    stdlib = sysconfig.get_paths().get("stdlib", "")
    if stdlib and normalised.startswith(_normalise(stdlib) + "/"):
        return "stdlib"

    return "benchmark"


#: How many of the hottest functions to name. Enough to see the shape of the
#: decode loop, short enough to read in a job summary.
_PROFILE_TOP = 8


def profile_case(operation: Callable[[], Any], iterations: int) -> dict[str, Any]:
    """Self time per package and per function, as fractions of the profiled total.

    cProfile charges every call an instrumentation cost, so the absolute
    numbers here are slower than the timings above and should not be quoted as
    throughput. What it is good for is the split: which package the
    interpreter is actually in when the work is being done, and which
    functions inside it.
    """
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(iterations):
        operation()
    profiler.disable()

    packages: collections.Counter = collections.Counter()
    functions = []
    for (filename, line, name), entry in pstats.Stats(profiler).stats.items():
        # entry is (primitive calls, total calls, self time, cumulative time,
        # callers). Total calls rather than primitive: the decoder's dispatch
        # recurses through every nested component, and the primitive count
        # hides exactly that.
        calls, self_time = entry[1], entry[2]
        package = _attribute(filename)
        packages[package] += self_time
        functions.append((self_time, calls, package, name, filename, line))

    grand_total = sum(packages.values())
    if not grand_total:
        return {"packages": {}, "functions": []}

    functions.sort(reverse=True)
    return {
        "packages": {
            name: packages[name] / grand_total
            for name in _ATTRIBUTION
            if packages[name]
        },
        "functions": [
            {
                "package": package,
                "function": f"{os.path.basename(filename)}:{line}({name})",
                "self_percent": self_time / grand_total * 100,
                "calls_per_op": calls / iterations,
            }
            for self_time, calls, package, name, filename, line in functions[
                :_PROFILE_TOP
            ]
        ],
    }


def run_profile(workload: Workload, iterations: int) -> dict[str, dict[str, Any]]:
    """Profile the pysnmp decode and encode path for one workload."""
    message_spec = rfc1901.Message()
    octets = workload.message_octets
    message = workload.message

    return {
        "decode": profile_case(
            lambda: decoder.decode(octets, asn1Spec=message_spec), iterations
        ),
        "encode": profile_case(lambda: encoder.encode(message), iterations),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def environment(codec: NetSnmpCodec | None) -> dict[str, Any]:
    """Everything needed to know what a number was measured on."""
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_compiler": platform.python_compiler(),
        # Free-threaded builds are a different interpreter for timing
        # purposes, and the version string alone does not say which one ran.
        "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pysnmp": getattr(pysnmp, "__version__", "unknown"),
        "pyasn1": getattr(pyasn1, "__version__", "unknown"),
        "netsnmp": None if codec is None else (codec.version or "unknown"),
        "netsnmp_library": None if codec is None else codec.path,
    }


def _table(measurements: list[Measurement]) -> list[str]:
    """The comparison, as markdown: one row per workload, layer and direction."""
    implementations = ["pysnmp", "pyasn1", "netsnmp"]
    present = [
        name
        for name in implementations
        if any(m.implementation == name for m in measurements)
    ]

    by_key: dict[tuple[str, str, str], dict[str, Measurement]] = {}
    for measurement in measurements:
        by_key.setdefault(measurement.key, {})[measurement.implementation] = measurement

    header = ["workload", "bindings", "layer", "direction"]
    header += [f"{name} (us/op)" for name in present]
    if "netsnmp" in present:
        header.append("pysnmp / netsnmp")
    if "pyasn1" in present:
        header.append("pysnmp / pyasn1")

    lines = ["| " + " | ".join(header) + " |"]
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    order = {name: index for index, (name, _, _) in enumerate(WORKLOADS)}
    for key in sorted(by_key, key=lambda k: (order.get(k[0], len(order)), k[1], k[2])):
        row_measurements = by_key[key]
        any_measurement = next(iter(row_measurements.values()))
        row = [key[0], str(any_measurement.varbinds), key[1], key[2]]
        for name in present:
            found = row_measurements.get(name)
            row.append(f"{found.usec_per_op:.2f}" if found else "--")

        pysnmp_result = row_measurements.get("pysnmp")
        for other in ("netsnmp", "pyasn1"):
            if other not in present:
                continue
            found = row_measurements.get(other)
            if pysnmp_result and found and found.usec_per_op:
                row.append(f"{pysnmp_result.usec_per_op / found.usec_per_op:.1f}x")
            else:
                row.append("--")

        lines.append("| " + " | ".join(row) + " |")

    return lines


def render_markdown(report: dict[str, Any]) -> str:
    """The whole report as markdown, for a job summary or an issue comment."""
    env = report["environment"]
    interpreter = f"{env['python_implementation']} {env['python_version']}"
    if env["free_threaded"]:
        interpreter += " (free-threaded)"

    lines = [
        "## BER codec benchmark",
        "",
        f"- **Interpreter**: {interpreter}",
        f"- **Platform**: {env['platform']} ({env['machine']})",
        f"- **pysnmp**: {env['pysnmp']}",
        f"- **pyasn1**: {env['pyasn1']}",
    ]
    if env["netsnmp"]:
        lines.append(f"- **net-snmp**: {env['netsnmp']} (`{env['netsnmp_library']}`)")
    else:
        lines.append("- **net-snmp**: not measured -- libnetsnmp was not loadable here")
    lines += [
        "",
        "Lower is better. Each figure is the fastest of "
        f"{report['measurements'][0]['repeats']} samples, each an average over "
        "an auto-sized run.",
        "",
    ]

    measurements = [Measurement(**m) for m in report["measurements"]]
    lines += _table(measurements)

    if report.get("profile"):
        lines += [
            "",
            "### Where the time goes",
            "",
            "Self time by package under cProfile, for the ten-binding message. "
            "Profiling inflates every call, so read the split, not the totals.",
            "",
            "| direction | " + " | ".join(_ATTRIBUTION) + " |",
            "|" + "|".join(["---"] * (len(_ATTRIBUTION) + 1)) + "|",
        ]
        for direction, result in report["profile"].items():
            split = result["packages"]
            row = [direction]
            row += [
                f"{split.get(name, 0.0) * 100:.1f}%" if name in split else "--"
                for name in _ATTRIBUTION
            ]
            lines.append("| " + " | ".join(row) + " |")

        for direction, result in report["profile"].items():
            if not result["functions"]:
                continue
            lines += [
                "",
                f"Hottest functions on {direction}, by self time:",
                "",
                "| package | function | self | calls/op |",
                "|---|---|---|---|",
            ]
            for entry in result["functions"]:
                lines.append(
                    f"| {entry['package']} | `{entry['function']}` "
                    f"| {entry['self_percent']:.1f}% "
                    f"| {entry['calls_per_op']:.0f} |"
                )

    if report.get("notes"):
        lines += ["", "### Notes", ""]
        lines += [f"- {note}" for note in report["notes"]]

    return "\n".join(lines) + "\n"


def render_text(report: dict[str, Any]) -> str:
    """The same report as a fixed-width table, for a terminal."""
    rendered = render_markdown(report)
    return "\n".join(
        line for line in rendered.splitlines() if not line.startswith("|---")
    )


# ---------------------------------------------------------------------------
# Putting several runs beside each other
# ---------------------------------------------------------------------------


def _label(env: dict[str, Any]) -> str:
    """How one run's environment reads in the cross-matrix table.

    ASCII only, here and in every other rendered line: the report is printed
    to a console as well as written to a file, and a Windows console is not
    UTF-8 -- a middle dot came back from the first CI run as a replacement
    character in the log.
    """
    system = env.get("platform", "").split("-")[0] or "unknown"
    interpreter = f"{env['python_implementation']} {env['python_version']}"
    if env.get("free_threaded"):
        interpreter += "t"
    return f"{system} / {interpreter}"


def load_reports(paths: list[str]) -> list[dict[str, Any]]:
    """Read every report named, following a directory to the JSON inside it."""
    reports = []
    for path in paths:
        if os.path.isdir(path):
            found = sorted(
                os.path.join(root, name)
                for root, _, names in os.walk(path)
                for name in names
                if name.endswith(".json")
            )
        else:
            found = [path]
        for name in found:
            with open(name, encoding="utf-8") as handle:
                reports.append(json.load(handle))
    return reports


def render_comparison(reports: list[dict[str, Any]]) -> str:
    """Every run's PDU figures in one table, one row per run and workload.

    This is what the matrix is for. A single number says how fast the codec is
    on one machine; the matrix says whether the answer depends on the platform
    or the interpreter, which is the part nobody could answer from the
    nine-year-old report -- it had CPython and PyPy figures and no way to tell
    which of the two differences mattered.
    """
    lines = [
        "## BER codec benchmark -- across the matrix",
        "",
        "PDU-layer figures, microseconds per operation, lower is better. The "
        "net-snmp columns are `libnetsnmp` through `ctypes` on the same octets, "
        "and are blank where the library was not installable on the runner.",
        "",
        "| run | workload | bindings | pysnmp decode | pysnmp encode "
        "| pyasn1 decode | netsnmp decode | pysnmp / netsnmp |",
        "|---|---|---|---|---|---|---|",
    ]

    order = {name: index for index, (name, _, _) in enumerate(WORKLOADS)}
    rows = []
    for report in reports:
        label = _label(report["environment"])
        figures: dict[str, dict[tuple[str, str], float]] = {}
        bindings: dict[str, int] = {}
        for measurement in report["measurements"]:
            if measurement["layer"] != "pdu":
                continue
            workload = measurement["workload"]
            figures.setdefault(workload, {})[
                (measurement["implementation"], measurement["direction"])
            ] = measurement["usec_per_op"]
            bindings[workload] = measurement["varbinds"]

        for workload, found in figures.items():
            pysnmp_decode = found.get(("pysnmp", "decode"))
            netsnmp_decode = found.get(("netsnmp", "decode"))
            ratio = (
                f"{pysnmp_decode / netsnmp_decode:.0f}x"
                if pysnmp_decode and netsnmp_decode
                else "--"
            )
            rows.append(
                (
                    label,
                    order.get(workload, len(order)),
                    [
                        label,
                        workload,
                        str(bindings[workload]),
                        _figure(found.get(("pysnmp", "decode"))),
                        _figure(found.get(("pysnmp", "encode"))),
                        _figure(found.get(("pyasn1", "decode"))),
                        _figure(netsnmp_decode),
                        ratio,
                    ],
                )
            )

    for _, _, row in sorted(rows, key=lambda entry: (entry[0], entry[1])):
        lines.append("| " + " | ".join(row) + " |")

    notes = [note for report in reports for note in report.get("notes", [])]
    if notes:
        lines += ["", "### Notes", ""]
        lines += [f"- {note}" for note in sorted(set(notes))]

    return "\n".join(lines) + "\n"


def _figure(value: float | None) -> str:
    """One measurement, or a dash where the run did not produce it."""
    return "--" if value is None else f"{value:.1f}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workload",
        action="append",
        choices=[name for name, _, _ in WORKLOADS],
        help="measure only this workload; repeatable (default: all of them)",
    )
    parser.add_argument(
        "--min-time",
        type=float,
        default=0.2,
        help="seconds one sample should last, which sets the iteration count",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="samples per case; the fastest is reported",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="a much shorter run, for checking the harness rather than the codec",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="also report self time by package under cProfile",
    )
    parser.add_argument(
        "--profile-iterations",
        type=int,
        default=200,
        help="how many operations to profile per direction",
    )
    parser.add_argument(
        "--no-netsnmp",
        action="store_true",
        help="skip the libnetsnmp baseline even where the library is present",
    )
    parser.add_argument(
        "--require-netsnmp",
        action="store_true",
        help="fail rather than carry on when libnetsnmp cannot be used",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="write the full report, samples included, as JSON",
    )
    parser.add_argument(
        "--markdown",
        metavar="PATH",
        help="write the report as markdown, for a job summary",
    )
    parser.add_argument(
        "--summarise",
        nargs="+",
        metavar="PATH",
        help=(
            "measure nothing; read these JSON reports, or the JSON under these "
            "directories, and print one table comparing them"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark and report."""
    args = parse_args(argv)

    if args.summarise:
        reports = load_reports(args.summarise)
        if not reports:
            print("error: no reports were found to summarise", file=sys.stderr)
            return 2
        comparison = render_comparison(reports)
        print(comparison)
        if args.markdown:
            with open(args.markdown, "w", encoding="utf-8") as handle:
                handle.write(comparison)
        return 0

    min_time = 0.02 if args.quick else args.min_time
    repeats = 2 if args.quick else args.repeats

    workloads = build_workloads(args.workload)
    notes = []

    codec: NetSnmpCodec | None = None
    if not args.no_netsnmp:
        try:
            codec = NetSnmpCodec()
            codec.self_check(workloads[0])
        except NetSnmpUnavailable as exc:
            if args.require_netsnmp:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            codec = None
            notes.append(f"net-snmp baseline skipped: {exc}")
        except OSError as exc:
            # A library that loads but then misbehaves on a call is still a
            # missing baseline, not a failed benchmark.
            if args.require_netsnmp:
                print(f"error: libnetsnmp failed: {exc}", file=sys.stderr)
                return 2
            codec = None
            notes.append(f"net-snmp baseline skipped: {exc}")

    measurements = run_benchmark(workloads, codec, min_time, repeats)

    profile: dict[str, dict[str, float]] = {}
    if args.profile:
        target = next((w for w in workloads if w.name == "poll"), workloads[0])
        iterations = 20 if args.quick else args.profile_iterations
        profile = run_profile(target, iterations)

    report = {
        "schema": 1,
        "environment": environment(codec),
        "workloads": [
            {
                "name": w.name,
                "description": w.description,
                "varbinds": w.varbinds,
                "message_octets": len(w.message_octets),
                "pdu_octets": len(w.pdu_octets),
            }
            for w in workloads
        ],
        "measurements": [asdict(m) for m in measurements],
        "profile": profile,
        "notes": notes,
    }

    print(render_text(report))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")

    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(report))

    return 0


if __name__ == "__main__":
    sys.exit(main())
