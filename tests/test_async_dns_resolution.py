"""Resolving a transport target's address must not stall the event loop.

`AbstractTransportTarget.__init__` called `_resolveAddr()`, and every
implementation of that calls `socket.getaddrinfo()` -- a blocking libc call.
Constructing a target is something an asyncio application does inside a
coroutine, so the whole loop stopped for the duration of the lookup:
milliseconds against a warm cache, the full resolver timeout against a DNS
server that is down. For a poller fanning out across thousands of hostnames
that cost is the dominant one, and it was entirely serialised.

A constructor cannot await, and there is no way to get a value back into one
without blocking the thread that has to produce it -- an executor future's
``result()`` from the loop thread raises, and a plain thread pool's blocks the
loop just as long. So resolution is deferred instead, and only when there is a
running loop to protect: with no loop there is nothing to stall, and the
constructor resolves exactly as it always did.
"""

import asyncio
import socket
import time

import pytest

from pysnmp.error import PySnmpError
from pysnmp.hlapi.asyncio.transport import UdpTransportTarget

#: Long enough that a stalled loop is unmistakable, short enough not to drag
#: the suite. The assertions compare orders of magnitude, not exact counts.
LOOKUP_SECONDS = 0.3

TICK_SECONDS = 0.01


@pytest.fixture
def slowResolver(monkeypatch):
    """Stand in for a slow DNS server, and count the lookups that happen."""
    real = socket.getaddrinfo
    calls = []

    def slow(host, port, *args, **kwargs):
        calls.append(host)
        time.sleep(LOOKUP_SECONDS)
        return real("127.0.0.1", port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", slow)

    return calls


async def _countTicks(stop):
    """How many times the loop got to run something else."""
    ticks = 0
    while not stop.is_set():
        ticks += 1
        await asyncio.sleep(TICK_SECONDS)

    return ticks


class TestTheLoopKeepsRunning:
    """The acceptance criterion the issue asks for."""

    def test_a_concurrent_task_makes_progress_during_the_lookup(self, slowResolver):
        async def run():
            stop = asyncio.Event()
            ticks = asyncio.create_task(_countTicks(stop))
            await asyncio.sleep(TICK_SECONDS * 2)  # let it get going

            target = UdpTransportTarget(("slow.invalid", 161))
            await target.resolve()

            stop.set()
            counted = await ticks

            # A stalled loop manages only the couple of ticks from before the
            # lookup started. A healthy one gets roughly LOOKUP_SECONDS /
            # TICK_SECONDS more; the floor is deliberately far below that so a
            # loaded CI runner cannot fail this on timing alone.
            assert counted > 10
            assert target.transportAddr == ("127.0.0.1", 161)

        asyncio.run(run())

    def test_the_constructor_itself_returns_immediately(self, slowResolver):
        async def run():
            started = time.monotonic()

            UdpTransportTarget(("slow.invalid", 161))

            assert time.monotonic() - started < LOOKUP_SECONDS / 2
            assert slowResolver == []  # nothing was looked up yet

        asyncio.run(run())


class TestOutsideALoopNothingChanges:
    """With no loop to protect, the old behaviour is the right behaviour."""

    def test_the_constructor_resolves(self, slowResolver):
        target = UdpTransportTarget(("slow.invalid", 161))

        assert target.isResolved
        assert target.transportAddr == ("127.0.0.1", 161)
        assert slowResolver == ["slow.invalid"]

    def test_repr_is_unchanged(self):
        assert repr(UdpTransportTarget(("127.0.0.1", 161))) == (
            "UdpTransportTarget(('127.0.0.1', 161), timeout=1, retries=5, tagList=b'')"
        )

    def test_resolve_is_a_no_op(self, slowResolver):
        target = UdpTransportTarget(("slow.invalid", 161))

        asyncio.run(target.resolve())

        assert slowResolver == ["slow.invalid"]  # not looked up a second time


class TestTheDeferredState:
    """What a target looks like between construction and resolution."""

    def test_it_reports_itself_unresolved(self, slowResolver):
        async def run():
            assert not UdpTransportTarget(("slow.invalid", 161)).isResolved

        asyncio.run(run())

    def test_reading_the_address_says_what_to_do(self, slowResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            # Loud rather than silent: a bare None reaching the LCD would surface
            # much further away as an unroutable target.
            with pytest.raises(PySnmpError, match="not resolved yet"):
                _ = target.transportAddr

            with pytest.raises(PySnmpError, match=r"resolve\(\)"):
                target.getTransportInfo()

        asyncio.run(run())

    def test_repr_does_not_raise(self, slowResolver):
        async def run():
            # repr() is most often reached while rendering something for a human,
            # a traceback included, so it shows the address as given rather than
            # raising over the one it does not have yet.
            target = UdpTransportTarget(("slow.invalid", 161))

            assert "slow.invalid" in repr(target)

        asyncio.run(run())


class TestResolvingOnce:
    """A target shared by a fan-out is looked up once, not once per request."""

    def test_concurrent_resolves_share_one_lookup(self, slowResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            await asyncio.gather(*(target.resolve() for _ in range(8)))

            assert slowResolver == ["slow.invalid"]
            assert target.transportAddr == ("127.0.0.1", 161)

        asyncio.run(run())

    def test_awaiting_again_does_not_look_up_again(self, slowResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            await target.resolve()
            await target.resolve()

            assert slowResolver == ["slow.invalid"]

        asyncio.run(run())

    def test_it_returns_self_so_it_can_be_awaited_inline(self, slowResolver):
        async def run():
            target = await UdpTransportTarget(("slow.invalid", 161)).resolve()

            assert target.transportAddr == ("127.0.0.1", 161)

        asyncio.run(run())


class TestTheHlapiResolvesBeforeUse:
    """The deferred state must never reach the LCD, which reads transportAddr."""

    def test_get_cmd_resolves_first(self, slowResolver, monkeypatch):
        async def run():
            from pysnmp.hlapi.asyncio import cmdgen

            seen = {}

            class Stop(Exception):
                pass

            def spy(snmpEngine, authData, transportTarget, *args, **kwargs):
                seen["resolved"] = transportTarget.isResolved
                raise Stop

            monkeypatch.setattr(cmdgen.lcd, "configure", spy)

            from pysnmp.entity.engine import SnmpEngine
            from pysnmp.hlapi.auth import CommunityData
            from pysnmp.hlapi.context import ContextData

            target = UdpTransportTarget(("slow.invalid", 161))

            with pytest.raises(Stop):
                await cmdgen.getCmd(
                    SnmpEngine(), CommunityData("public"), target, ContextData()
                )

            assert seen["resolved"] is True

        asyncio.run(run())


class TestOnlyBlockingResolutionIsDeferred:
    """A transport that looks nothing up has no reason to defer.

    ``UnixTransportTarget._resolveAddr`` only checks that it was handed a path
    string -- there is no lookup and nothing that could stall a loop. Deferring
    it anyway would buy nothing and would cost something: a bad path would stop
    being rejected by the constructor and would surface later, from ``resolve``,
    somewhere further from the mistake.
    """

    def test_a_unix_target_resolves_in_the_constructor_inside_a_loop(self):
        from pysnmp.hlapi.asyncio.transport import UnixTransportTarget

        async def run():
            target = UnixTransportTarget("/tmp/agent.sock")

            assert target.isResolved
            assert target.transportAddr == "/tmp/agent.sock"

        asyncio.run(run())

    def test_a_bad_path_is_still_rejected_by_the_constructor(self):
        from pysnmp.hlapi.asyncio.transport import UnixTransportTarget

        async def run():
            with pytest.raises(PySnmpError, match="expected a path string"):
                UnixTransportTarget(123)

        asyncio.run(run())

    def test_an_ip_target_does_defer(self, slowResolver):
        async def run():
            assert not UdpTransportTarget(("slow.invalid", 161)).isResolved

        asyncio.run(run())


@pytest.fixture
def failingResolver(monkeypatch):
    """Stand in for a resolver that is down, and count the attempts."""
    calls = []

    def failing(host, port, *args, **kwargs):
        calls.append(host)
        raise socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution")

    monkeypatch.setattr(socket, "getaddrinfo", failing)

    return calls


class TestCancellingACallerKeepsTheLookup:
    """Giving up on a request must not throw away a lookup already in flight.

    ``run_in_executor`` hands the work to a thread, and a thread that has
    started cannot be called off. So the result arrives whatever the caller
    does: if cancelling the caller discarded it, the next ``resolve()`` on the
    same target would start the whole lookup again -- the full resolver timeout
    a second time, exactly where a shared target was supposed to pay it once.
    """

    def test_a_cancelled_caller_does_not_cause_a_second_lookup(self, slowResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            first = asyncio.create_task(target.resolve())
            await asyncio.sleep(TICK_SECONDS * 2)  # let the lookup get going
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first

            # The lookup the cancelled caller started is still in flight; this
            # one waits on it rather than starting its own.
            await target.resolve()

            assert slowResolver == ["slow.invalid"]
            assert target.transportAddr == ("127.0.0.1", 161)

        asyncio.run(run())

    def test_a_result_that_lands_with_nobody_waiting_is_still_kept(self, slowResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            first = asyncio.create_task(target.resolve())
            await asyncio.sleep(TICK_SECONDS * 2)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first

            # Nothing is awaiting the lookup when the executor thread finishes.
            await asyncio.sleep(LOOKUP_SECONDS)

            assert target.isResolved  # the result was taken off it anyway

            await target.resolve()

            assert slowResolver == ["slow.invalid"]
            assert target.transportAddr == ("127.0.0.1", 161)

        asyncio.run(run())

    def test_one_cancelled_caller_does_not_cancel_the_others(self, slowResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            waiting = [asyncio.create_task(target.resolve()) for _ in range(4)]
            await asyncio.sleep(TICK_SECONDS * 2)
            waiting[0].cancel()

            with pytest.raises(asyncio.CancelledError):
                await waiting[0]

            assert await asyncio.gather(*waiting[1:]) == [target] * 3
            assert slowResolver == ["slow.invalid"]
            assert target.transportAddr == ("127.0.0.1", 161)

        asyncio.run(run())

    def test_cancelling_does_not_wait_for_the_lookup(self, slowResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            first = asyncio.create_task(target.resolve())
            await asyncio.sleep(TICK_SECONDS * 2)

            # Keeping the lookup alive must not make the caller that no longer
            # wants it wait for it: a request giving up never blocks on DNS.
            started = time.monotonic()
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first

            assert time.monotonic() - started < LOOKUP_SECONDS / 2

        asyncio.run(run())


class TestAFailedLookupIsTriedAgain:
    """A resolver that was down is not an answer to cache."""

    def test_the_error_reaches_the_caller(self, failingResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            with pytest.raises(PySnmpError):
                await target.resolve()

        asyncio.run(run())

    def test_a_later_caller_looks_up_again(self, failingResolver):
        async def run():
            target = UdpTransportTarget(("slow.invalid", 161))

            for _ in range(2):
                with pytest.raises(PySnmpError):
                    await target.resolve()

            assert failingResolver == ["slow.invalid"] * 2

        asyncio.run(run())
