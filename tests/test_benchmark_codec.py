"""The codec benchmark's harness, checked for the things a number depends on.

A benchmark nobody tests is a number generator. What these establish is not
how fast anything is -- CI timings are not repeatable enough to assert on --
but that the thing being timed is the thing the report says it is:

* the workloads are real SNMPv2c responses that round-trip;
* the bare-pyasn1 mirror decodes pysnmp's own octets to the same values, so
  the ``pysnmp`` and ``pyasn1`` columns are two ways of doing one job rather
  than two different jobs;
* the profile attributes pyasn1's frames to pyasn1, which a checkout of this
  repository -- itself a directory called ``pysnmp`` -- makes easy to get
  backwards;
* the report has the shape the workflow reads.
"""

import json
import sys
from pathlib import Path

import pytest
from pyasn1.codec.ber import decoder, encoder

from pysnmp.proto import rfc1901, rfc1905
from pysnmp.proto.api import v2c

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import benchmark_codec  # noqa: E402


@pytest.fixture(scope="module")
def workloads():
    """Every workload the benchmark defines, built once."""
    return benchmark_codec.build_workloads()


class TestWorkloads:
    def test_every_declared_workload_is_built(self, workloads):
        assert [w.name for w in workloads] == [
            name for name, _, _ in benchmark_codec.WORKLOADS
        ]

    def test_selection_by_name(self):
        selected = benchmark_codec.build_workloads(["poll"])
        assert [w.name for w in selected] == ["poll"]

    def test_binding_counts_match_the_declaration(self, workloads):
        declared = {name: count for name, _, count in benchmark_codec.WORKLOADS}
        for workload in workloads:
            assert workload.varbinds == declared[workload.name]
            assert len(v2c.apiPDU.getVarBinds(workload.pdu)) == workload.varbinds

    def test_messages_round_trip_through_pysnmp(self, workloads):
        for workload in workloads:
            decoded, trailing = decoder.decode(
                workload.message_octets, asn1Spec=rfc1901.Message()
            )
            assert trailing == b""
            assert v2c.apiMessage.getCommunity(decoded).asOctets() == b"public"
            assert v2c.apiPDU.getVarBinds(
                v2c.apiMessage.getPDU(decoded)
            ) == v2c.apiPDU.getVarBinds(workload.pdu)

    def test_pdu_octets_are_the_pdu_inside_the_message(self, workloads):
        for workload in workloads:
            assert workload.pdu_octets in workload.message_octets

    def test_a_poll_carries_more_than_one_syntax(self, workloads):
        # The mix is the point: one syntax repeated would measure one decoder
        # path and call it a poll.
        poll = next(w for w in workloads if w.name == "poll")
        syntaxes = {
            type(value).__name__ for _, value in v2c.apiPDU.getVarBinds(poll.pdu)
        }
        assert len(syntaxes) > 3


class TestBarePyasn1Mirror:
    """The mirror has to be the same message, not merely a similar one."""

    def test_mirror_decodes_pysnmp_octets(self, workloads):
        for workload in workloads:
            decoded, trailing = decoder.decode(
                workload.message_octets, asn1Spec=benchmark_codec.BareMessage()
            )
            assert trailing == b""
            assert bytes(decoded["community"]) == b"public"

    def test_mirror_recovers_the_same_values(self, workloads):
        for workload in workloads:
            mirrored, _ = decoder.decode(
                workload.pdu_octets, asn1Spec=benchmark_codec.BarePDUs()
            )
            original = v2c.apiPDU.getVarBinds(workload.pdu)
            bindings = mirrored.getComponent()["variable-bindings"]

            assert len(bindings) == len(original)
            for (name, value), binding in zip(original, bindings):
                assert tuple(binding["name"]) == tuple(name)
                # The mirror's leaves are bare pyasn1 types, so the objects
                # will not compare equal to pysnmp's -- a Counter32 arrives as
                # a plain APPLICATION 1 Integer. What has to match is the
                # value and its tags, and re-encoding says both at once.
                assert encoder.encode(binding[""].getComponent()) == encoder.encode(
                    value
                )

    def test_mirror_reencodes_to_the_same_octets(self, workloads):
        # Same structure, same tags, same lengths: if the mirror re-encoded to
        # anything else it would be decoding something else too.
        for workload in workloads:
            mirrored, _ = decoder.decode(
                workload.message_octets, asn1Spec=benchmark_codec.BareMessage()
            )
            assert encoder.encode(mirrored) == workload.message_octets

    def test_mirror_carries_every_pdu_alternative(self):
        # Dispatching through an eight-alternative choice is what the protocol
        # costs. Dropping the alternatives the benchmark does not send would
        # make the mirror cheaper than the spec it stands in for.
        assert len(benchmark_codec.BarePDUs().componentType) == len(
            rfc1905.PDUs().componentType
        )

    def test_mirror_carries_no_constraints(self):
        # The mirror exists to have no subtype specs; if one turned up, the
        # pysnmp-versus-pyasn1 column would be measuring nothing.
        assert not benchmark_codec.BareCounter32().subtypeSpec
        assert not benchmark_codec.BareVarBindList().subtypeSpec


class TestProfileAttribution:
    def test_pyasn1_frames_are_attributed_to_pyasn1(self):
        import pyasn1.codec.ber.decoder as pyasn1_decoder

        assert benchmark_codec._attribute(pyasn1_decoder.__file__) == "pyasn1"

    def test_pysnmp_frames_are_attributed_to_pysnmp(self):
        assert benchmark_codec._attribute(rfc1905.__file__) == "pysnmp"

    def test_the_harness_is_not_counted_as_either(self):
        assert benchmark_codec._attribute(benchmark_codec.__file__) == "benchmark"

    def test_builtins_are_recognised(self):
        assert benchmark_codec._attribute("~") == "builtins"

    def test_stdlib_frames_are_attributed_to_the_stdlib(self):
        assert benchmark_codec._attribute(json.__file__) == "stdlib"

    def test_the_split_adds_up(self, workloads):
        poll = next(w for w in workloads if w.name == "poll")
        profile = benchmark_codec.run_profile(poll, iterations=3)

        for direction in ("decode", "encode"):
            packages = profile[direction]["packages"]
            assert packages
            assert abs(sum(packages.values()) - 1.0) < 1e-6
            assert set(packages) <= set(benchmark_codec._ATTRIBUTION)
            # The finding this benchmark exists to state: the codec is where
            # the time is, and the codec is pyasn1's.
            assert packages["pyasn1"] > 0.5

    def test_hot_functions_are_reported_with_their_call_counts(self, workloads):
        poll = next(w for w in workloads if w.name == "poll")
        profile = benchmark_codec.run_profile(poll, iterations=3)

        functions = profile["decode"]["functions"]
        assert functions
        assert all(entry["calls_per_op"] > 0 for entry in functions)
        # Sorted by self time, hottest first.
        assert functions == sorted(
            functions, key=lambda e: e["self_percent"], reverse=True
        )


class TestTiming:
    def test_autorange_grows_until_the_sample_is_long_enough(self):
        calls = []
        iterations = benchmark_codec._autorange(lambda: calls.append(1), 0.01)
        assert iterations >= 1
        assert len(calls) >= iterations

    def test_measure_returns_one_sample_per_repeat(self):
        iterations, samples = benchmark_codec.measure(
            lambda: None, 0.001, repeats=3, warmups=0
        )
        assert iterations >= 1
        assert len(samples) == 3
        assert all(sample > 0 for sample in samples)

    def test_warmup_samples_run_and_are_not_reported(self):
        # A tracing JIT charges the first case measured for compiling the
        # decoder. Discarded samples are how that stops landing in a figure,
        # so they have to actually run -- and not turn up as extra samples.
        calls = []
        iterations, samples = benchmark_codec.measure(
            lambda: calls.append(1), 0.001, repeats=2, warmups=3
        )

        assert len(samples) == 2
        assert len(calls) >= iterations * 5

    def test_cpython_needs_no_warmup_samples(self):
        # And they are not free, so nothing pays for them where the first call
        # is already enough.
        expected = 0 if sys.implementation.name == "cpython" else 3
        assert expected == benchmark_codec._WARMUP_SAMPLES


class TestMeasuringOrder:
    """Which implementation runs first, and whether the report says so."""

    def test_no_implementation_is_always_measured_first(self, workloads):
        poll = next(w for w in workloads if w.name == "poll")
        cases = benchmark_codec._interleave(
            benchmark_codec._pysnmp_cases(poll) + benchmark_codec._pyasn1_cases(poll)
        )

        leaders = [group[0] for group in _grouped(cases).values()]
        # Measuring every pysnmp case before every pyasn1 case puts a
        # workload's worth of runner drift between two figures that are then
        # compared with each other, and that drift is larger than the
        # difference being measured.
        assert len(set(leaders)) > 1, "one implementation led every group"

    def test_corresponding_cases_are_measured_together(self, workloads):
        poll = next(w for w in workloads if w.name == "poll")
        cases = benchmark_codec._interleave(
            benchmark_codec._pysnmp_cases(poll) + benchmark_codec._pyasn1_cases(poll)
        )

        # Every (layer, direction) group is contiguous: nothing else is
        # measured between two figures that get divided by each other.
        seen = []
        for layer, direction, _, _ in cases:
            if not seen or seen[-1] != (layer, direction):
                seen.append((layer, direction))
        assert len(seen) == len(set(seen))

    def test_every_case_still_runs(self, workloads):
        poll = next(w for w in workloads if w.name == "poll")
        original = benchmark_codec._pysnmp_cases(poll) + benchmark_codec._pyasn1_cases(
            poll
        )
        reordered = benchmark_codec._interleave(original)

        assert len(reordered) == len(original)
        assert {case[:3] for case in reordered} == {case[:3] for case in original}


def _grouped(cases):
    """The cases by (layer, direction), in the order they are measured."""
    groups = {}
    for layer, direction, implementation, _ in cases:
        groups.setdefault((layer, direction), []).append(implementation)
    return groups


class TestReport:
    """The shape the workflow and any later comparison read."""

    def test_end_to_end_run_writes_the_reports(self, tmp_path):
        json_path = tmp_path / "results.json"
        markdown_path = tmp_path / "summary.md"

        exit_code = benchmark_codec.main(
            [
                "--quick",
                "--workload",
                "single",
                "--profile",
                "--json",
                str(json_path),
                "--markdown",
                str(markdown_path),
            ]
        )
        assert exit_code == 0

        report = json.loads(json_path.read_text(encoding="utf-8"))
        assert report["schema"] == 1
        assert report["environment"]["pysnmp"]
        assert report["environment"]["pyasn1"]
        assert report["workloads"][0]["name"] == "single"

        implementations = {m["implementation"] for m in report["measurements"]}
        assert {"pysnmp", "pyasn1"} <= implementations

        # The measuring order is the order of this list, and each entry says
        # where it fell -- see TestMeasuringOrder for why that is not the
        # order of the table.
        sequences = [m["sequence"] for m in report["measurements"]]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == len(sequences)

        for measurement in report["measurements"]:
            assert measurement["usec_per_op"] > 0
            assert measurement["ops_per_sec"] > 0
            assert measurement["samples"]
            assert measurement["layer"] in ("message", "pdu")
            assert measurement["direction"] in ("decode", "encode")

        summary = markdown_path.read_text(encoding="utf-8")
        assert "## BER codec benchmark" in summary
        assert "| workload |" in summary
        assert "Where the time goes" in summary
        # The profile describes whichever workload was profiled, which is not
        # always the ten-binding one: this run built only `single`.
        assert report["profiled_workload"] == {"name": "single", "varbinds": 1}
        assert "1-binding message (`single`)" in summary

    def test_comparison_table_delimiters_match_its_header(self, tmp_path):
        # A delimiter row that disagrees with the header row renders the whole
        # table as literal text on GitHub, which is where this one is read.
        json_path = tmp_path / "results.json"
        assert (
            benchmark_codec.main(
                ["--quick", "--workload", "single", "--json", str(json_path)]
            )
            == 0
        )

        comparison = benchmark_codec.render_comparison(
            benchmark_codec.load_reports([str(json_path)])
        )
        rows = [line for line in comparison.splitlines() if line.startswith("|")]
        widths = {line.count("|") for line in rows}
        assert len(widths) == 1, f"ragged table: {widths}"

    def test_comparison_names_the_versions_only_when_they_differ(self):
        # Comparing releases runs one interpreter against several pysnmp
        # versions, so the platform and interpreter -- all the label used to
        # carry -- are identical on every row. Without the version the table
        # is rows of numbers nobody can attribute.
        def report(pysnmp_version):
            return {
                "environment": {
                    "platform": "Linux-6.1-x86_64",
                    "python_implementation": "CPython",
                    "python_version": "3.14.0",
                    "pysnmp": pysnmp_version,
                    "pyasn1": "2.0.6",
                },
                "measurements": [
                    {
                        "workload": "poll",
                        "layer": "pdu",
                        "direction": "decode",
                        "implementation": "pysnmp",
                        "usec_per_op": 1.0,
                        "varbinds": 10,
                    }
                ],
            }

        one_version = benchmark_codec.render_comparison([report("6.0.0")])
        assert "Linux / CPython 3.14.0 |" in one_version
        assert "pysnmp 6.0.0 +" not in one_version

        two_versions = benchmark_codec.render_comparison(
            [report("6.0.0"), report("7.1.29")]
        )
        assert "pysnmp 6.0.0 + pyasn1 2.0.6" in two_versions
        assert "pysnmp 7.1.29 + pyasn1 2.0.6" in two_versions

        # Still one row per report: the label tells them apart, it does not
        # merge or duplicate them.
        rows = [
            line
            for line in two_versions.splitlines()
            if line.startswith("|") and "poll" in line
        ]
        assert len(rows) == 2

    def test_netsnmp_can_be_required(self, monkeypatch, tmp_path):
        # Whether the baseline is present is a property of the runner, so the
        # benchmark carries on without it by default. --require-netsnmp is
        # what a job that means to compare uses, and it has to fail rather
        # than quietly report half a table.
        def unavailable(*args, **kwargs):
            raise benchmark_codec.NetSnmpUnavailable("not here")

        monkeypatch.setattr(benchmark_codec, "NetSnmpCodec", unavailable)

        assert (
            benchmark_codec.main(
                ["--quick", "--workload", "single", "--require-netsnmp"]
            )
            == 2
        )

    def test_missing_netsnmp_is_a_note_not_a_failure(self, monkeypatch, capsys):
        def unavailable(*args, **kwargs):
            raise benchmark_codec.NetSnmpUnavailable("not here")

        monkeypatch.setattr(benchmark_codec, "NetSnmpCodec", unavailable)

        assert benchmark_codec.main(["--quick", "--workload", "single"]) == 0
        assert "net-snmp baseline skipped" in capsys.readouterr().out


@pytest.fixture(scope="module")
def codec():
    """The libnetsnmp binding, where the shared library is installed."""
    try:
        return benchmark_codec.NetSnmpCodec()
    except benchmark_codec.NetSnmpUnavailable as exc:
        pytest.skip(f"libnetsnmp unavailable: {exc}")


class TestNetSnmpBaseline:
    """Only where libnetsnmp is installed -- skipped everywhere else."""

    def test_round_trip_through_libnetsnmp_preserves_the_bindings(
        self, codec, workloads
    ):
        for workload in workloads:
            codec.self_check(workload)

    def test_a_truncated_pdu_is_reported_rather_than_timed(self, codec, workloads):
        poll = next(w for w in workloads if w.name == "poll")
        with pytest.raises(benchmark_codec.NetSnmpUnavailable):
            codec.parse(poll.pdu_octets[:-20])
