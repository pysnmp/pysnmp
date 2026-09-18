"""RFC 2578 counters wrap at their ceiling rather than overflowing.

Counter32, Counter64 and TimeTicks are each defined to increase until they
reach their maximum, "when it wraps around and starts increasing again from
zero". Nothing implemented that, so crossing the ceiling raised
ValueConstraintError out of pyasn1's constraint check -- in two places where
there is nowhere useful for that to surface: ``sysUpTime``, which every
notification carries and the command responder reads, and the engine's own
statistics counters, which are advanced with ``+=`` on the receive path.
"""

import time

import pytest
from pyasn1.error import PyAsn1Error

from pysnmp.proto.rfc1902 import (
    Counter32,
    Counter64,
    Gauge32,
    Integer32,
    TimeTicks,
    Unsigned32,
)
from pysnmp.smi.builder import MibBuilder

CEILING32 = 2**32 - 1
CEILING64 = 2**64 - 1

WRAPPING = [
    pytest.param(Counter32, CEILING32, id="Counter32"),
    pytest.param(TimeTicks, CEILING32, id="TimeTicks"),
    pytest.param(Counter64, CEILING64, id="Counter64"),
]


@pytest.mark.parametrize(("cls", "ceiling"), WRAPPING)
def test_one_past_the_ceiling_is_zero(cls, ceiling):
    assert cls(ceiling) + 1 == 0


@pytest.mark.parametrize(("cls", "ceiling"), WRAPPING)
def test_the_wrap_keeps_counting(cls, ceiling):
    assert cls(ceiling) + 3 == 2


@pytest.mark.parametrize(("cls", "ceiling"), WRAPPING)
def test_augmented_assignment_wraps(cls, ceiling):
    # The form the engine actually uses -- `counter.syntax += 1` -- which
    # reaches __add__ through Python's fallback for +=.
    counter = cls(ceiling - 1)
    counter += 1
    counter += 1
    counter += 1

    assert counter == 1


@pytest.mark.parametrize(("cls", "ceiling"), WRAPPING)
def test_ordinary_addition_is_unchanged(cls, ceiling):
    assert cls(5) + 3 == 8
    assert cls(5) + cls(3) == 8
    assert 3 + cls(5) == 8


@pytest.mark.parametrize(("cls", "ceiling"), WRAPPING)
def test_the_result_keeps_its_type(cls, ceiling):
    assert isinstance(cls(ceiling) + 1, cls)


@pytest.mark.parametrize(("cls", "ceiling"), WRAPPING)
def test_adding_a_non_integer_is_still_a_type_error(cls, ceiling):
    # The wrap must not widen what counts as addable.
    with pytest.raises(TypeError):
        cls(1) + "2"


@pytest.mark.parametrize(
    "cls", [Gauge32, Unsigned32, Integer32], ids=["Gauge32", "Unsigned32", "Integer32"]
)
def test_the_non_wrapping_types_still_refuse_to_overflow(cls):
    # A Gauge latches at its maximum rather than wrapping (RFC 2578 section
    # 7.1.7), and Integer32 has no wrap either. Pinned so the change is not
    # later generalised onto them.
    with pytest.raises(PyAsn1Error):
        cls(cls.subtypeSpec[-1].stop) + 1


class TestSysUpTime:
    """The 497-day case, which is what made this urgent."""

    @pytest.fixture
    def sysUpTime(self):
        built = MibBuilder()
        (symbol,) = built.importSymbols("__SNMPv2-MIB", "sysUpTime")

        return symbol.syntax

    def test_it_reads_normally_at_a_sane_uptime(self, sysUpTime):
        sysUpTime.createdAt = time.time() - 60

        assert 5900 <= int(sysUpTime.clone()) <= 6100

    def test_it_still_reads_past_the_ceiling(self, sysUpTime):
        # 2**32 / 100 seconds is roughly 497 days. Before the wrap, every read
        # from this moment on raised and the agent stopped answering.
        sysUpTime.createdAt = time.time() - (2**32 / 100 + 10)

        assert int(sysUpTime.clone()) == pytest.approx(1000, abs=100)

    def test_an_explicit_value_is_still_honoured(self, sysUpTime):
        assert int(sysUpTime.clone(value=42)) == 42


class TestStatisticsCounters:
    """The other half: counters the engine advances with ``+=``."""

    @pytest.mark.parametrize(
        "symbol",
        [
            "usmStatsWrongDigests",
            "usmStatsUnknownUserNames",
            "usmStatsNotInTimeWindows",
            "usmStatsDecryptionErrors",
        ],
    )
    def test_a_usm_statistic_wraps_where_the_security_model_bumps_it(self, symbol):
        # Driven through the same expression secmod/rfc3414/service.py uses,
        # on the same MIB instance object, rather than on a bare Counter32.
        built = MibBuilder()
        built.loadModules("__SNMP-USER-BASED-SM-MIB")
        (instance,) = built.importSymbols("__SNMP-USER-BASED-SM-MIB", symbol)

        instance.syntax = instance.syntax.clone(CEILING32)
        instance.syntax += 1

        assert int(instance.syntax) == 0

    def test_an_mpd_statistic_wraps_where_message_processing_bumps_it(self):
        built = MibBuilder()
        built.loadModules("__SNMPv2-MIB")
        (instance,) = built.importSymbols("__SNMPv2-MIB", "snmpInPkts")

        instance.syntax = instance.syntax.clone(CEILING32)
        instance.syntax += 1

        assert int(instance.syntax) == 0
