"""A request timeout is measured on the dispatcher's clock, so the clock has to fit.

A target's timeout is stored faithfully -- in centiseconds, on
``snmpTargetAddrTimeout`` -- and then expires on a counter that advances once
per the dispatcher's timer resolution, 0.5 seconds by default. So a timeout
finer than that could not be measured at all: it was accepted, reported back by
``__repr__``, and rounded up to the next tick by the thing that acts on it.
"""

import warnings

import pytest

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.auth import CommunityData
from pysnmp.hlapi.lcd import (
    MIN_TIMER_RESOLUTION,
    TICKS_PER_TIMEOUT,
    CommandGeneratorLcdConfigurator,
)

#: What AbstractTransportDispatcher starts with.
DEFAULT_RESOLUTION = 0.5


class StubTransportTarget:
    """Enough of a transport target for the configurator, without a socket."""

    transportDomain = udp.domainName
    transportAddr = ("127.0.0.1", 161)
    iface = None
    retries = 1

    def __init__(self, timeout, tagList=b""):
        self.timeout = timeout
        self.tagList = tagList

    def verifyDispatcherCompatibility(self, snmpEngine):
        pass

    def openClientMode(self):
        return udp.UdpTransport().openClientMode()


@pytest.fixture
def configured():
    """Configure targets on one engine, and read its resolution back."""
    snmpEngine = SnmpEngine()
    configurator = CommandGeneratorLcdConfigurator()
    community = iter(f"community-{n}" for n in range(100))

    def configure(timeout, tagList=b""):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            configurator.configure(
                snmpEngine,
                CommunityData(next(community)),
                StubTransportTarget(timeout, tagList),
            )

        return snmpEngine.transportDispatcher.getTimerResolution()

    return configure


class TestTimerResolutionFollowsTheFinestTimeout:
    def test_the_default_timeout_leaves_the_clock_alone(self, configured):
        # 1 second against a 0.5 second tick is already two ticks. Nothing about
        # the stock configuration should move.
        assert configured(1.0) == DEFAULT_RESOLUTION

    def test_a_coarser_timeout_leaves_the_clock_alone(self, configured):
        assert configured(5.0) == DEFAULT_RESOLUTION

    @pytest.mark.parametrize("timeout", [0.5, 0.2, 0.1, 0.02])
    def test_a_finer_timeout_lowers_the_clock_to_measure_it(self, configured, timeout):
        # The reported case: timeout=0.2 used to wait for the next 0.5 second
        # tick instead.
        resolution = configured(timeout)

        assert resolution == timeout / TICKS_PER_TIMEOUT

    @pytest.mark.parametrize("timeout", [1.0, 0.5, 0.2, 0.1, 0.02])
    def test_the_timeout_still_spans_two_ticks(self, configured, timeout):
        # What the caller asked for, measured the way the engine measures it:
        # entity/rfc3413/cmdgen.py computes float(centiseconds) / 100 /
        # resolution and expiry counts that many ticks.
        resolution = configured(timeout)
        ticks = (timeout * 100) / 100 / resolution

        assert ticks == pytest.approx(TICKS_PER_TIMEOUT)
        assert ticks * resolution == pytest.approx(timeout)

    def test_a_timeout_below_the_floor_is_honoured_as_far_as_it_can_be(
        self, configured
    ):
        # The dispatcher refuses anything finer than 10ms, and the tick drives a
        # periodic callback whose cost is not free. Clamp rather than raise: a
        # caller asking for a very small timeout should not have configure()
        # blow up in their face.
        assert configured(0.005) == MIN_TIMER_RESOLUTION

    def test_the_clock_is_never_raised_back(self, configured):
        # Resolution is dispatcher-wide while timeouts are per-target, so a
        # later coarse target must not undo a finer one's setting.
        assert configured(0.2, b"a") == 0.1
        assert configured(5.0, b"b") == 0.1

    def test_the_finest_target_wins(self, configured):
        assert configured(0.2, b"a") == 0.1
        assert configured(0.05, b"b") == 0.025
        assert configured(1.0, b"c") == 0.025

    def test_a_timeout_of_zero_leaves_the_clock_alone(self, configured):
        # 0 means "do not wait", which needs no clock at all -- and dividing it
        # down would ask the dispatcher for a resolution of 0.
        assert configured(0) == DEFAULT_RESOLUTION
