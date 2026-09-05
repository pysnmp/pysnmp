"""Pins what the verifyConstraints/matchTags/matchConstraints flags actually do.

pysnmp passes these three flags to pyasn1 setters in roughly forty places. The
audit in #154 established two things about them that are not obvious from the
call sites, and that decide whether any given one is removable:

- for a raw Python value the flags change nothing, because pyasn1 clones the
  value into the slot's own type and that clone verifies unconditionally;
- for an already-constructed pyasn1 object they skip the compatibility check
  entirely, and pyasn1 compares constraint objects structurally rather than by
  range.

The second is why three of the sites are load-bearing: a MIB-sourced Integer32
carries a ConstraintsIntersection that differs structurally from the plain
Integer the protocol slot declares, even when the numeric bounds agree. Remove
the flags there and every outgoing message raises.

These tests fail if pyasn1 changes either behaviour, which is exactly when the
bypasses should be revisited.
"""

import pytest
from pyasn1.error import PyAsn1Error, ValueConstraintError
from pyasn1.type import constraint, namedtype, univ

from pysnmp.entity.engine import SnmpEngine
from pysnmp.proto.mpmod.rfc3412 import HeaderData
from pysnmp.proto.secmod.rfc3414.service import UsmSecurityParameters

FLAGS = {"verifyConstraints": False, "matchTags": False, "matchConstraints": False}


class Constrained(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType(
            "value",
            univ.Integer().subtype(subtypeSpec=constraint.ValueRangeConstraint(0, 100)),
        )
    )


class TestFlagSemantics:
    def test_raw_value_is_verified_despite_the_flags(self):
        """A raw int is cloned into the slot's type, and the clone verifies."""
        with pytest.raises(ValueConstraintError):
            Constrained().setComponentByPosition(0, 999999, **FLAGS)

    def test_constructed_object_is_not_verified(self):
        """An already-built object skips the check and reaches the encoder."""
        from pyasn1.codec.ber import encoder

        seq = Constrained()
        seq.setComponentByPosition(0, univ.Integer(999999), **FLAGS)
        assert int(seq.getComponentByPosition(0)) == 999999
        assert encoder.encode(seq)


class TestLoadBearingBypasses:
    """The three sites where removing the flags breaks message generation."""

    @pytest.fixture(scope="class")
    @staticmethod
    def mib_builder():
        return SnmpEngine().msgAndPduDsp.mibInstrumController.mibBuilder

    @pytest.mark.parametrize(
        ("spec", "position", "symbol"),
        [
            (HeaderData, 1, "snmpEngineMaxMessageSize"),
            (UsmSecurityParameters, 1, "snmpEngineBoots"),
            (UsmSecurityParameters, 2, "snmpEngineTime"),
        ],
    )
    def test_mib_scalar_is_rejected_by_a_strict_set(self, mib_builder, spec, position, symbol):
        (scalar,) = mib_builder.importSymbols("__SNMP-FRAMEWORK-MIB", symbol)
        message = spec()

        with pytest.raises(PyAsn1Error, match="tag-incompatible"):
            message.setComponentByPosition(position, scalar.syntax)

        message.setComponentByPosition(position, scalar.syntax, **FLAGS)
        assert int(message.getComponentByPosition(position)) == int(scalar.syntax)
