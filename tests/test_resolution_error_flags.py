"""Telling a name that will not resolve apart from a value that will not cast.

`ignoreErrors` covered both, which meant a response path had to choose between
two unrelated things. A name the peer answered under a MIB this side has not
loaded has to stay tolerated -- walking a device whose vendor MIBs you do not
have is routine, and raising would end the walk at its first such binding. A
value that contradicts the syntax its own MIB declares is a real disagreement
with the peer, and tolerating it hands the caller the uncast value rendered
with the wrong textual convention and nothing to say why.

`ignoreValueErrors` separates them, so a caller can be told about the second
without being stopped by the first.
"""

import pytest

from pysnmp.proto.rfc1902 import Integer, OctetString
from pysnmp.smi import builder, error, view
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

# sysServices is INTEGER (0..127), so 200 is a value no conforming agent sends
# and a value the MIB cannot represent.
OUT_OF_RANGE = 200

# Under `enterprises`, in a subtree no bundled MIB defines.
UNKNOWN_OID = "1.3.6.1.4.1.9999.1.2.3.0"


@pytest.fixture
def mvc():
    return view.MibViewController(builder.MibBuilder())


def sysServices(value):
    return ObjectType(ObjectIdentity("SNMPv2-MIB", "sysServices", 0), value)


class TestAValueThatContradictsItsMib:
    """The failure worth reporting."""

    def test_reported_when_asked_for(self, mvc):
        ot = sysServices(Integer(OUT_OF_RANGE))

        with pytest.raises(error.SmiError, match="failed to cast value"):
            ot.resolveWithMib(mvc, ignoreValueErrors=False)

    def test_tolerated_by_default(self, mvc):
        # Unchanged: the uncast value comes back, which is what every caller
        # gets today and what this must keep doing until asked otherwise.
        ot = sysServices(Integer(OUT_OF_RANGE))

        ot.resolveWithMib(mvc)

        assert ot[1] == Integer(OUT_OF_RANGE)

    def test_none_follows_ignore_errors(self, mvc):
        # The default is "whatever ignoreErrors said", so a caller that was
        # already passing ignoreErrors=False keeps the behaviour it had.
        ot = sysServices(Integer(OUT_OF_RANGE))

        with pytest.raises(error.SmiError, match="failed to cast value"):
            ot.resolveWithMib(mvc, ignoreErrors=False, ignoreValueErrors=None)

    def test_it_overrides_ignore_errors(self, mvc):
        # The point of splitting them: tolerate names, report values.
        ot = sysServices(Integer(OUT_OF_RANGE))

        with pytest.raises(error.SmiError, match="failed to cast value"):
            ot.resolveWithMib(mvc, ignoreErrors=True, ignoreValueErrors=False)

    def test_and_the_other_way_round(self, mvc):
        ot = sysServices(Integer(OUT_OF_RANGE))

        ot.resolveWithMib(mvc, ignoreErrors=False, ignoreValueErrors=True)

        assert ot[1] == Integer(OUT_OF_RANGE)

    def test_a_conforming_value_still_casts(self, mvc):
        ot = sysServices(Integer(72))

        ot.resolveWithMib(mvc, ignoreValueErrors=False)

        assert ot[1] == 72


class TestANameUnderAnUnloadedMib:
    """The failure that must stay tolerated, or walks stop working."""

    @pytest.mark.parametrize("ignore_value_errors", [None, True, False])
    def test_it_is_never_raised_for(self, mvc, ignore_value_errors):
        # This is the binding a walk gets back from a device whose vendor MIB
        # is not loaded. Reporting it would end the walk here.
        ot = ObjectType(ObjectIdentity(UNKNOWN_OID), OctetString("vendor"))

        ot.resolveWithMib(mvc, ignoreValueErrors=ignore_value_errors)

        assert ot[0].prettyPrint().endswith("enterprises.9999.1.2.3.0")
        assert ot[1] == OctetString("vendor")

    @pytest.mark.parametrize("ignore_value_errors", [None, True, False])
    def test_a_subtree_root_still_starts_a_walk(self, mvc, ignore_value_errors):
        # 1.3.6.1.2.1.1 is `system`; next_cmd and bulk_cmd are started from it.
        ot = ObjectType(ObjectIdentity("1.3.6.1.2.1.1"))

        assert ot.resolveWithMib(mvc, ignoreValueErrors=ignore_value_errors) is ot


class TestTheResponsePath:
    """What `unmakeVarBinds` does with it, since that is what callers reach."""

    @pytest.fixture
    def processor(self):
        from pysnmp.hlapi.varbinds import CommandGeneratorVarBinds

        return CommandGeneratorVarBinds()

    @pytest.fixture
    def engine(self):
        from pysnmp.entity.engine import SnmpEngine

        return SnmpEngine()

    def _binding(self, value):
        return [(ObjectIdentity("SNMPv2-MIB", "sysServices", 0), value)]

    def test_tolerant_by_default(self, processor, engine):
        (bound,) = processor.unmakeVarBinds(
            engine, self._binding(Integer(OUT_OF_RANGE))
        )

        assert bound[1] == Integer(OUT_OF_RANGE)

    def test_reports_when_asked(self, processor, engine):
        with pytest.raises(error.SmiError, match="failed to cast value"):
            processor.unmakeVarBinds(
                engine, self._binding(Integer(OUT_OF_RANGE)), True, False
            )

    def test_lookup_off_looks_nothing_up(self, processor, engine):
        # Nothing is resolved, so there is nothing for the flag to report on.
        varBinds = self._binding(Integer(OUT_OF_RANGE))

        assert processor.unmakeVarBinds(engine, varBinds, False, False) is varBinds

    def test_an_unloaded_mib_is_still_tolerated(self, processor, engine):
        (bound,) = processor.unmakeVarBinds(
            engine,
            [(ObjectIdentity(UNKNOWN_OID), OctetString("vendor"))],
            True,
            False,
        )

        assert bound[1] == OctetString("vendor")
