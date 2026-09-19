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
        iterations, samples = benchmark_codec.measure(lambda: None, 0.001, repeats=3)
        assert iterations >= 1
        assert len(samples) == 3
        assert all(sample > 0 for sample in samples)


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
