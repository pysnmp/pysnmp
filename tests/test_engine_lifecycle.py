"""The engine's dispatcher lifecycle: closing it, and the context manager forms.

Shutting an engine down used to mean knowing to call
``transportDispatcher.closeDispatcher()`` and ``unregisterTransportDispatcher()``
in that order. Forgetting the second left the dispatcher holding its socket, which
is a descriptor leak with nothing in the traceback to point at. These tests cover
the single call that replaces the pair, and the ``with``/``async with`` forms that
run it on the exception path too.
"""

import asyncio
import gc
import os
import platform
import warnings
from pathlib import Path

import pytest

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.stream import tcp
from pysnmp.carrier.error import CarrierError
from pysnmp.entity import config
from pysnmp.entity.engine import SnmpEngine

LOCALHOST = ("127.0.0.1", 0)


def _openFdCount() -> int:
    """How many descriptors this process holds, on a platform that will say.

    Counted after finalisation has actually run, which is not free on every
    interpreter. CPython closes a socket the moment its last reference goes,
    so the count is already right; PyPy collects, queues finalisers and runs
    them on a later pass, so a count taken straight after the work reads every
    not-yet-finalised socket as a leak. Fifty cycles of this test read 209
    descriptors against a baseline of 9 on PyPy, and 5 after the collections
    below -- nothing was leaking, the descriptors had simply not been closed
    yet.

    Collecting to a fixed point rather than a set number of times: how many
    passes it takes is an implementation detail, and on PyPy it took three.
    """
    if platform.python_implementation() != "CPython":
        previous = -1
        for _ in range(10):
            gc.collect()
            current = len(os.listdir("/proc/self/fd"))
            if current == previous:
                break
            previous = current

    return len(os.listdir("/proc/self/fd"))


needsProcFs = pytest.mark.skipif(
    not Path("/proc/self/fd").is_dir(),
    reason="descriptor counting needs /proc, which this platform does not have",
)


class TestCloseDispatcher:
    def test_closes_and_unregisters_in_one_call(self):
        engine = SnmpEngine()
        config.addTransport(
            engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
        )
        assert engine.transportDispatcher is not None

        engine.closeDispatcher()

        assert engine.transportDispatcher is None

    def test_is_idempotent(self):
        engine = SnmpEngine()
        config.addTransport(
            engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
        )

        engine.closeDispatcher()
        engine.closeDispatcher()  # the second must not raise

        assert engine.transportDispatcher is None

    def test_is_a_no_op_without_a_dispatcher(self):
        # Reaching a state that already holds is not an error.
        SnmpEngine().closeDispatcher()

    def test_detaches_even_when_the_dispatcher_raises_on_close(self):
        class Failing(AsyncioDispatcher):
            def closeDispatcher(self):
                raise RuntimeError("boom")

        engine = SnmpEngine()
        engine.registerTransportDispatcher(Failing())

        with pytest.raises(RuntimeError, match="boom"):
            engine.closeDispatcher()

        # An engine still pointing at a half-closed dispatcher would refuse to
        # register another one.
        assert engine.transportDispatcher is None
        engine.registerTransportDispatcher(AsyncioDispatcher())
        engine.closeDispatcher()


class TestOpenDispatcher:
    def test_is_a_no_op_without_a_dispatcher(self):
        SnmpEngine().openDispatcher()

    def test_passes_the_timeout_to_the_registered_dispatcher(self):
        # Not run for real: with nothing outstanding `runDispatcher()` serves
        # until the loop is stopped, which is the point of it but not testable
        # in one process. What is worth pinning is that the call reaches the
        # dispatcher, with the timeout the caller gave.
        seen = []

        class Recording(AsyncioDispatcher):
            def runDispatcher(self, timeout=0.0):
                seen.append(timeout)

        engine = SnmpEngine()
        engine.registerTransportDispatcher(Recording())

        engine.openDispatcher(timeout=1.5)

        assert seen == [1.5]
        engine.closeDispatcher()


class TestContextManager:
    def test_sync_form_closes_on_the_normal_path(self):
        with SnmpEngine() as engine:
            config.addTransport(
                engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
            )
            assert engine.transportDispatcher is not None

        assert engine.transportDispatcher is None

    def test_sync_form_closes_on_the_exception_path(self):
        engine = SnmpEngine()

        with pytest.raises(ValueError, match="deliberate"), engine:
            config.addTransport(
                engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
            )
            raise ValueError("deliberate")

        assert engine.transportDispatcher is None

    def test_async_form_closes_on_the_normal_path(self):
        async def run():
            async with SnmpEngine() as engine:
                config.addTransport(
                    engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
                )
                assert engine.transportDispatcher is not None
            return engine

        assert asyncio.run(run()).transportDispatcher is None

    def test_async_form_closes_on_the_exception_path(self):
        engine = SnmpEngine()

        async def run():
            async with engine:
                config.addTransport(
                    engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
                )
                raise ValueError("deliberate")

        with pytest.raises(ValueError, match="deliberate"):
            asyncio.run(run())

        assert engine.transportDispatcher is None

    def test_async_form_is_a_no_op_without_a_dispatcher(self):
        async def run():
            async with SnmpEngine() as engine:
                assert engine.transportDispatcher is None

        asyncio.run(run())

    def test_sync_form_inside_a_running_loop_closes_but_warns(self):
        engine = SnmpEngine()

        async def run():
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                with engine:
                    config.addTransport(
                        engine,
                        udp.domainName,
                        udp.UdpAsyncioTransport().openClientMode(),
                    )
                return caught

        caught = asyncio.run(run())

        # The sockets are released either way -- that is the leak worth
        # preventing -- but the timer could not be awaited, so say which form
        # does not have that problem.
        assert engine.transportDispatcher is None
        assert any(
            issubclass(w.category, RuntimeWarning) and "async with" in str(w.message)
            for w in caught
        ), [str(w.message) for w in caught]


class TestDescriptorLeak:
    @needsProcFs
    def test_repeated_create_and_close_leaks_nothing(self):
        def cycle():
            with SnmpEngine() as engine:
                config.addTransport(
                    engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
                )

        cycle()  # once first, so one-off allocations are not counted as growth
        before = _openFdCount()

        for _ in range(50):
            cycle()

        # An exact match would be brittle -- the interpreter may open something
        # of its own during the run -- but a per-cycle leak shows up as ~50.
        assert _openFdCount() - before < 10


class TestDelTransport:
    def test_closes_a_dispatcher_it_created_itself(self):
        engine = SnmpEngine()
        config.addTransport(
            engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
        )

        config.delTransport(engine, udp.domainName)

        assert engine.transportDispatcher is None

    def test_leaves_a_dispatcher_the_caller_registered(self):
        engine = SnmpEngine()
        mine = AsyncioDispatcher()
        engine.registerTransportDispatcher(mine)
        config.addTransport(
            engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
        )

        config.delTransport(engine, udp.domainName)

        assert engine.transportDispatcher is mine
        engine.closeDispatcher()

    def test_does_not_adopt_a_later_dispatcher_the_caller_registered(self):
        """The counter's name, not its value, is what gets dropped on teardown.

        Dropping the value left the real entry behind at zero, so the next
        `addTransport()` read a dispatcher the caller had registered as one this
        module created, and `delTransport()` then closed it out from under them --
        which is exactly what that function documents it will not do.
        """
        engine = SnmpEngine()
        config.addTransport(
            engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
        )
        config.delTransport(engine, udp.domainName)
        assert engine.transportDispatcher is None

        mine = AsyncioDispatcher()
        engine.registerTransportDispatcher(mine)
        config.addTransport(
            engine, udp.domainName, udp.UdpAsyncioTransport().openClientMode()
        )

        config.delTransport(engine, udp.domainName)

        assert engine.transportDispatcher is mine
        engine.closeDispatcher()


class TestClosedLoopGuard:
    def test_open_client_mode_on_a_closed_loop_says_so(self):
        loop = asyncio.new_event_loop()
        transport = udp.UdpAsyncioTransport(loop=loop)
        loop.close()

        with pytest.raises(CarrierError, match="already been closed"):
            transport.openClientMode()

    def test_open_server_mode_on_a_closed_loop_says_so(self):
        loop = asyncio.new_event_loop()
        transport = udp.UdpAsyncioTransport(loop=loop)
        loop.close()

        with pytest.raises(CarrierError, match="already been closed"):
            transport.openServerMode(LOCALHOST)

    def test_stream_open_server_mode_on_a_closed_loop_says_so(self):
        loop = asyncio.new_event_loop()
        transport = tcp.TcpAsyncioTransport(loop=loop)
        loop.close()

        with pytest.raises(CarrierError, match="already been closed"):
            transport.openServerMode(LOCALHOST)

    def test_a_live_loop_is_not_refused(self):
        loop = asyncio.new_event_loop()
        try:
            udp.UdpAsyncioTransport(loop=loop).openClientMode()
        finally:
            loop.close()
