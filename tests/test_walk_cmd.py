"""Subtree-bounded walking: where it stops, and what it says when it cannot.

GETNEXT and GETBULK run lexicographically over the whole MIB, so a caller asking
for one subtree gets rows from outside it unless someone bounds the walk. Four
separate reports upstream came from getting that wrong, so the edges are pinned
here rather than left to the integration suite: where the walk stops, how a
GETBULK overshoot is trimmed, and that an agent's refusal is distinguishable
from the table simply ending.
"""

import asyncio

import pytest

from pysnmp.hlapi.asyncio import SnmpEngine, bulk_walk_cmd, walk_cmd
from pysnmp.hlapi.asyncio import cmdgen as async_cmdgen
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import Integer, OctetString
from pysnmp.proto.rfc1905 import endOfMibView
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

# Two columns of a small table, and one object past the end of it. A walk of
# `IN_SUBTREE` must stop before `PAST_END`.
SUBTREE = (1, 3, 6, 1, 2, 1, 2, 2, 1, 2)
PAST_END = (1, 3, 6, 1, 2, 1, 2, 2, 1, 3)


def oid(*suffix):
    return SUBTREE + suffix


class _Agent:
    """Answers GETNEXT/GETBULK from a fixed lexicographic list of bindings."""

    def __init__(self, bindings, errorAt=None, errorIndication=None):
        self.bindings = bindings
        self.errorAt = errorAt
        self.errorIndication = errorIndication
        self.calls = 0
        self.maxRepetitionsSeen = []

    def _after(self, name):
        for candidate, value in self.bindings:
            if tuple(candidate) > tuple(name):
                return candidate, value
        return None

    async def next_cmd(self, _engine, _auth, _target, _context, *varBinds, **_options):
        self.calls += 1
        if self.errorAt is not None and self.calls >= self.errorAt:
            return self.errorIndication, 0, 0, []
        row = []
        for name, _ in varBinds:
            nxt = self._after(tuple(name))
            row.append(nxt if nxt is not None else (name, endOfMibView))
        return None, 0, 0, [row]

    async def bulk_cmd(
        self,
        _engine,
        _auth,
        _target,
        _context,
        _nonRepeaters,
        maxRepetitions,
        *varBinds,
        **_options,
    ):
        self.calls += 1
        self.maxRepetitionsSeen.append(maxRepetitions)
        if self.errorAt is not None and self.calls >= self.errorAt:
            return self.errorIndication, 0, 0, []
        table = []
        cursor = [tuple(name) for name, _ in varBinds]
        for _ in range(maxRepetitions):
            row = []
            for column, name in enumerate(cursor):
                nxt = self._after(name)
                if nxt is None:
                    row.append((name, endOfMibView))
                else:
                    row.append(nxt)
                    cursor[column] = tuple(nxt[0])
            table.append(row)
        return None, 0, 0, table


@pytest.fixture
def table():
    """Three rows in the subtree, then one object outside it."""
    return [
        (oid(1), OctetString("eth0")),
        (oid(2), OctetString("eth1")),
        (oid(3), OctetString("eth2")),
        (PAST_END + (1,), Integer(6)),
    ]


def drive(generator):
    """Run an async generator to exhaustion, collecting what it yielded."""

    async def run():
        return [item async for item in generator]

    return asyncio.run(run())


def walk(agent, monkeypatch, **options):
    monkeypatch.setattr(async_cmdgen, "next_cmd", agent.next_cmd)
    return drive(
        walk_cmd(
            SnmpEngine(),
            None,
            None,
            None,
            ObjectType(ObjectIdentity(SUBTREE)),
            **options,
        )
    )


def bulkWalk(agent, monkeypatch, maxRepetitions=10, **options):
    monkeypatch.setattr(async_cmdgen, "bulk_cmd", agent.bulk_cmd)
    return drive(
        bulk_walk_cmd(
            SnmpEngine(),
            None,
            None,
            None,
            0,
            maxRepetitions,
            ObjectType(ObjectIdentity(SUBTREE)),
            **options,
        )
    )


def names(rows):
    return [tuple(row[3][0][0]) for row in rows]


class TestWalkStopsAtTheSubtree:
    def test_rows_outside_the_subtree_are_not_yielded(self, table, monkeypatch):
        # The whole point: PAST_END is lexicographically next, and GETNEXT will
        # happily return it. A walk must not.
        rows = walk(_Agent(table), monkeypatch)
        assert names(rows) == [oid(1), oid(2), oid(3)]

    def test_lexicographic_mode_runs_past_the_end(self, table, monkeypatch):
        rows = walk(_Agent(table), monkeypatch, lexicographicMode=True)
        assert names(rows) == [oid(1), oid(2), oid(3), PAST_END + (1,)]

    def test_an_empty_subtree_yields_nothing(self, monkeypatch):
        rows = walk(_Agent([(PAST_END + (1,), Integer(6))]), monkeypatch)
        assert rows == []

    def test_end_of_mib_ends_the_walk(self, monkeypatch):
        rows = walk(_Agent([(oid(1), OctetString("eth0"))]), monkeypatch)
        assert names(rows) == [oid(1)]


class TestWalkBounds:
    def test_max_rows_stops_the_walk(self, table, monkeypatch):
        rows = walk(_Agent(table), monkeypatch, maxRows=2)
        assert names(rows) == [oid(1), oid(2)]

    def test_max_calls_stops_the_walk(self, table, monkeypatch):
        agent = _Agent(table)
        rows = walk(agent, monkeypatch, maxCalls=1)
        assert len(rows) == 1
        assert agent.calls == 1

    def test_stopping_early_stops_requesting(self, table, monkeypatch):
        # Leaving the loop must not keep polling the agent -- that is most of
        # why this is a generator rather than a list.
        agent = _Agent(table)
        monkeypatch.setattr(async_cmdgen, "next_cmd", agent.next_cmd)

        async def run():
            async for _ in walk_cmd(
                SnmpEngine(), None, None, None, ObjectType(ObjectIdentity(SUBTREE))
            ):
                break

        asyncio.run(run())
        assert agent.calls == 1


class TestWalkReportsFailure:
    def test_an_error_is_yielded_before_the_walk_ends(self, table, monkeypatch):
        # A generator that just returns on an error is indistinguishable from
        # one that ran out of subtree, so the caller cannot tell "the table
        # ended" from "the agent refused".
        agent = _Agent(table, errorAt=2, errorIndication=errind.requestTimedOut)
        rows = walk(agent, monkeypatch)

        assert len(rows) == 2
        assert rows[0][0] is None
        assert rows[-1][0] is errind.requestTimedOut

    def test_an_immediate_error_is_still_yielded(self, table, monkeypatch):
        agent = _Agent(table, errorAt=1, errorIndication=errind.requestTimedOut)
        rows = walk(agent, monkeypatch)

        assert len(rows) == 1
        assert rows[0][0] is errind.requestTimedOut

    def test_a_non_increasing_oid_ends_the_walk_by_default(self, table, monkeypatch):
        agent = _Agent(table, errorAt=1, errorIndication=errind.OidNotIncreasing())
        rows = walk(agent, monkeypatch)

        assert len(rows) == 1
        assert isinstance(rows[0][0], errind.OidNotIncreasing)

    def test_ignore_non_increasing_oid_carries_on(self, table, monkeypatch):
        # A non-increasing OID is a common agent defect; this is the knob that
        # lets a walk survive one.
        agent = _Agent(table, errorAt=2, errorIndication=errind.OidNotIncreasing())
        rows = walk(agent, monkeypatch, ignoreNonIncreasingOid=True)

        assert all(row[0] is None for row in rows)


class TestBulkWalk:
    def test_the_overshoot_is_trimmed(self, table, monkeypatch):
        # GETBULK fills maxRepetitions rows whether or not they are in the
        # subtree. Asking for 10 against a 3-row table is the case that
        # produced the upstream reports.
        rows = bulkWalk(_Agent(table), monkeypatch, maxRepetitions=10)
        assert names(rows) == [oid(1), oid(2), oid(3)]

    def test_a_single_row_response_past_the_end_stops(self, table, monkeypatch):
        # maxRepetitions=1 is the shape of etingof/pysnmp#270: when the whole
        # response is one row and that row has left the subtree, the walk has
        # to stop rather than mark the column and carry on.
        rows = bulkWalk(_Agent(table), monkeypatch, maxRepetitions=1)
        assert names(rows) == [oid(1), oid(2), oid(3)]

    def test_lexicographic_mode_keeps_the_overshoot(self, table, monkeypatch):
        rows = bulkWalk(
            _Agent(table), monkeypatch, maxRepetitions=10, lexicographicMode=True
        )
        assert PAST_END + (1,) in names(rows)

    def test_max_rows_bounds_what_is_requested(self, table, monkeypatch):
        # Never make the agent build rows that will be thrown away.
        agent = _Agent(table)
        rows = bulkWalk(agent, monkeypatch, maxRepetitions=10, maxRows=2)
        assert len(rows) == 2
        assert agent.maxRepetitionsSeen == [2]

    def test_an_error_is_yielded(self, table, monkeypatch):
        agent = _Agent(table, errorAt=1, errorIndication=errind.requestTimedOut)
        rows = bulkWalk(agent, monkeypatch)
        assert len(rows) == 1
        assert rows[0][0] is errind.requestTimedOut


class TestYieldShape:
    def test_a_row_unpacks_positionally(self, table, monkeypatch):
        errorIndication, errorStatus, errorIndex, varBinds = walk(
            _Agent(table), monkeypatch
        )[0]
        assert errorIndication is None
        assert errorIndex == 0
        assert tuple(varBinds[0][0]) == oid(1)

    def test_a_row_also_has_named_fields(self, table, monkeypatch):
        row = walk(_Agent(table), monkeypatch)[0]
        assert row.errorIndication is None
        assert row.errorStatus == 0
        assert tuple(row.varBinds[0][0]) == oid(1)


class TestDeprecatedSpellings:
    def test_walk_cmd_has_a_camel_case_alias(self):
        import pysnmp.hlapi.asyncio as hlapi

        with pytest.warns(DeprecationWarning, match=r"walkCmd\(\) is deprecated"):
            assert hlapi.walkCmd is walk_cmd

    def test_bulk_walk_cmd_has_a_camel_case_alias(self):
        import pysnmp.hlapi.asyncio as hlapi

        with pytest.warns(DeprecationWarning, match=r"bulkWalkCmd\(\) is deprecated"):
            assert hlapi.bulkWalkCmd is bulk_walk_cmd
