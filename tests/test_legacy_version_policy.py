"""An engine can be built unable to speak SNMPv1 and SNMPv2c.

The question this answers is an auditor's, not a packager's: *can this engine
accept a community-authenticated request?* Uninstalling something on a build
host does not answer it, and neither does a check the application makes before
it calls pysnmp. Only what the engine will do with the bytes answers it.

So the mechanism is subtraction rather than a check. The v1 and v2c message
processing models are simply not registered, and `MsgAndPduDispatcher` already
knows what to do with a message whose version it has no model for -- RFC 3412
section 4.2.1.2, count it in `snmpInBadVersions` and drop it. There is no new
code on the receive path that could be wrong, and no order of operations in
which a message is parsed first and rejected second.

What is tested here is that subtraction, from both directions, plus the two
ways to ask for it and the error a caller gets for configuring a community on
an engine that has none.
"""

import warnings

import pytest
from pyasn1.codec.ber import encoder

from pysnmp import error
from pysnmp.entity import config, engine
from pysnmp.entity.engine import LEGACY_VERSIONS_ENV
from pysnmp.proto import api, errind
from pysnmp.proto import error as protoError
from pysnmp.proto.mpmod.rfc2576 import (
    SnmpV1MessageProcessingModel,
    SnmpV2cMessageProcessingModel,
)
from pysnmp.proto.mpmod.rfc3412 import SnmpV3MessageProcessingModel
from pysnmp.proto.secmod.rfc2576 import SnmpV1SecurityModel, SnmpV2cSecurityModel
from pysnmp.proto.secmod.rfc3414 import SnmpUSMSecurityModel

V1 = SnmpV1MessageProcessingModel.messageProcessingModelID
V2C = SnmpV2cMessageProcessingModel.messageProcessingModelID
V3 = SnmpV3MessageProcessingModel.messageProcessingModelID

#: A transport domain and address the dispatcher will accept as provenance.
UDP_IPV4 = (1, 3, 6, 1, 6, 1, 1)
FROM = ("127.0.0.1", 44444)


def communityRequest(protoVersion: int) -> bytes:
    """A real, well-formed community-authenticated GET, on the wire.

    Built rather than hard-coded, because a hand-written byte string that the
    decoder rejects would fail these tests for the wrong reason -- and would
    keep passing the negative test while proving nothing.

    Args:
        protoVersion: ``api.protoVersion1`` or ``api.protoVersion2c``

    Returns:
        The BER-encoded message.
    """
    protoModule = api.protoModules[protoVersion]

    request = protoModule.GetRequestPDU()
    protoModule.apiPDU.setDefaults(request)
    protoModule.apiPDU.setVarBinds(
        request,
        ((protoModule.ObjectIdentifier("1.3.6.1.2.1.1.1.0"), protoModule.Null("")),),
    )

    message = protoModule.Message()
    protoModule.apiMessage.setDefaults(message)
    protoModule.apiMessage.setCommunity(message, "public")
    protoModule.apiMessage.setPDU(message, request)

    return encoder.encode(message)


@pytest.fixture(autouse=True)
def _noEnvironmentPolicy(monkeypatch):
    """Answer to the constructor, not to whoever ran the suite.

    Every test here either sets the variable itself or means to test the
    default, and a developer with it exported would otherwise see the second
    kind pass for the wrong reason.
    """
    monkeypatch.delenv(LEGACY_VERSIONS_ENV, raising=False)


@pytest.fixture
def quiet():
    """Suppress the v1/v2c warning, for tests not about the warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", error.PySnmpWeakCryptoWarning)
        yield


class TestTheDefaultIsUnchanged:
    """Existing v1/v2c deployments must not notice this landed."""

    def test_all_three_versions_are_registered(self):
        assert set(engine.SnmpEngine().messageProcessingSubsystems) == {V1, V2C, V3}

    def test_all_three_security_models_are_registered(self):
        assert set(engine.SnmpEngine().securityModels) == {
            SnmpV1SecurityModel.securityModelID,
            SnmpV2cSecurityModel.securityModelID,
            SnmpUSMSecurityModel.securityModelID,
        }

    def test_a_community_can_still_be_configured(self, quiet):
        snmpEngine = engine.SnmpEngine()
        config.addV1System(snmpEngine, "my-area", "public")

        assert snmpEngine.enableLegacyVersions is True


class TestDisablingRemovesTheModels:
    """Subtraction, checked as subtraction."""

    @pytest.fixture
    def v3Only(self):
        return engine.SnmpEngine(enableLegacyVersions=False)

    def test_only_v3_message_processing_remains(self, v3Only):
        assert set(v3Only.messageProcessingSubsystems) == {V3}

    def test_only_usm_remains(self, v3Only):
        assert set(v3Only.securityModels) == {SnmpUSMSecurityModel.securityModelID}

    @pytest.mark.parametrize("version", (V1, V2C))
    def test_a_legacy_version_has_no_handler(self, v3Only, version):
        assert version not in v3Only.messageProcessingSubsystems

    def test_the_engine_says_so(self, v3Only):
        assert v3Only.enableLegacyVersions is False


class TestOutboundIsRefused:
    """`sendPdu` raises rather than serializing something unauthenticated."""

    def test_sending_v2c_raises_unsupported_model(self):
        snmpEngine = engine.SnmpEngine(enableLegacyVersions=False)

        with pytest.raises(protoError.StatusInformation) as caught:
            snmpEngine.msgAndPduDsp.sendPdu(
                snmpEngine,
                transportDomain=UDP_IPV4,
                transportAddress=("127.0.0.1", 161),
                messageProcessingModel=V2C,
                securityModel=2,
                securityName="whatever",
                securityLevel=1,
                contextEngineId=None,
                contextName=b"",
                pduVersion=1,
                PDU=None,
                expectResponse=False,
            )

        assert caught.value["errorIndication"] == errind.unsupportedMsgProcessingModel

    def test_sending_v3_is_not_affected(self):
        # Not that v3 succeeds -- there is no transport here -- but that it
        # gets past the model lookup, which is the only thing being removed.
        snmpEngine = engine.SnmpEngine(enableLegacyVersions=False)

        with pytest.raises(Exception) as caught:  # noqa: B017, PT011
            snmpEngine.msgAndPduDsp.sendPdu(
                snmpEngine,
                transportDomain=UDP_IPV4,
                transportAddress=("127.0.0.1", 161),
                messageProcessingModel=V3,
                securityModel=3,
                securityName="whatever",
                securityLevel=1,
                contextEngineId=None,
                contextName=b"",
                pduVersion=1,
                PDU=None,
                expectResponse=False,
            )

        assert (
            getattr(caught.value, "get", lambda _: None)("errorIndication")
            != errind.unsupportedMsgProcessingModel
        )


class TestInboundIsCounted:
    """RFC 3412 4.2.1.2: an unknown version is counted and dropped.

    Nothing here is new behaviour -- it is what the dispatcher has always done
    with a version it has no model for. That is the reason for implementing
    the policy this way, so it is worth a test that says so.
    """

    @staticmethod
    def badVersions(snmpEngine):
        (counter,) = (
            snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                "__SNMPv2-MIB", "snmpInBadVersions"
            )
        )

        return int(counter.syntax)

    @pytest.mark.parametrize(
        "protoVersion", (api.protoVersion1, api.protoVersion2c), ids=("v1", "v2c")
    )
    def test_a_legacy_message_is_counted_and_dropped(self, protoVersion):
        snmpEngine = engine.SnmpEngine(enableLegacyVersions=False)
        before = self.badVersions(snmpEngine)

        snmpEngine.msgAndPduDsp.receiveMessage(
            snmpEngine, UDP_IPV4, FROM, communityRequest(protoVersion)
        )

        assert self.badVersions(snmpEngine) == before + 1

    @pytest.mark.parametrize(
        "protoVersion", (api.protoVersion1, api.protoVersion2c), ids=("v1", "v2c")
    )
    def test_the_same_message_is_not_counted_by_default(self, protoVersion):
        # The counter must move because the model is gone, not because the
        # message was rejected on its own merits -- so the identical bytes
        # must leave it alone on an engine that has the model. Without this
        # the test above passes for a malformed message.
        snmpEngine = engine.SnmpEngine()
        before = self.badVersions(snmpEngine)

        snmpEngine.msgAndPduDsp.receiveMessage(
            snmpEngine, UDP_IPV4, FROM, communityRequest(protoVersion)
        )

        assert self.badVersions(snmpEngine) == before


class TestConfiguringACommunityFailsEarly:
    """Where the mistake is, rather than at the first send."""

    def test_add_v1_system_raises(self):
        snmpEngine = engine.SnmpEngine(enableLegacyVersions=False)

        with pytest.raises(error.PySnmpError, match="SNMPv1/v2c disabled"):
            config.addV1System(snmpEngine, "my-area", "public")

    def test_the_error_names_both_ways_back(self):
        snmpEngine = engine.SnmpEngine(enableLegacyVersions=False)

        with pytest.raises(error.PySnmpError) as caught:
            config.addV1System(snmpEngine, "my-area", "public")

        assert "enableLegacyVersions=True" in str(caught.value)
        assert LEGACY_VERSIONS_ENV in str(caught.value)

    def test_adding_a_v3_user_is_unaffected(self):
        snmpEngine = engine.SnmpEngine(enableLegacyVersions=False)
        config.addV3User(
            snmpEngine,
            "usr",
            config.usmHMACSHAAuthProtocol,
            "authkey1",
            config.usmAesCfb128Protocol,
            "privkey1",
        )

        (usmUserEntry,) = snmpEngine.getMibBuilder().importSymbols(
            "SNMP-USER-BASED-SM-MIB", "usmUserEntry"
        )

        assert usmUserEntry is not None


class TestTheEnvironmentVariable:
    """The lever for an application nobody is going to edit."""

    @pytest.mark.parametrize("value", ("1", "true", "TRUE", "yes", "on", " yes "))
    def test_a_truthy_value_disables(self, monkeypatch, value):
        monkeypatch.setenv(LEGACY_VERSIONS_ENV, value)

        assert engine.SnmpEngine().enableLegacyVersions is False

    @pytest.mark.parametrize("value", ("0", "false", "no", "", "off", "maybe"))
    def test_anything_else_leaves_it_alone(self, monkeypatch, value):
        monkeypatch.setenv(LEGACY_VERSIONS_ENV, value)

        assert engine.SnmpEngine().enableLegacyVersions is True

    def test_an_explicit_argument_wins_over_the_environment(self, monkeypatch):
        # The variable is an operator's default, not an override. An
        # application that deliberately builds a legacy engine -- a proxy
        # translating v2c to v3, say -- must still be able to.
        monkeypatch.setenv(LEGACY_VERSIONS_ENV, "1")

        assert engine.SnmpEngine(enableLegacyVersions=True).enableLegacyVersions is True

    def test_it_is_read_at_construction_not_at_import(self, monkeypatch):
        # Otherwise a process that sets the variable during start-up, after
        # something has already imported pysnmp, gets silently ignored.
        assert engine.SnmpEngine().enableLegacyVersions is True

        monkeypatch.setenv(LEGACY_VERSIONS_ENV, "1")

        assert engine.SnmpEngine().enableLegacyVersions is False


class TestTheWarning:
    """A deprecation path, ahead of any change of default."""

    def test_configuring_a_community_warns(self):
        snmpEngine = engine.SnmpEngine()

        with pytest.warns(error.PySnmpWeakCryptoWarning, match="cleartext"):
            config.addV1System(snmpEngine, "my-area", "public")

    def test_the_warning_says_how_to_enforce_the_policy(self):
        snmpEngine = engine.SnmpEngine()

        with pytest.warns(error.PySnmpWeakCryptoWarning) as caught:
            config.addV1System(snmpEngine, "my-area", "public")

        assert LEGACY_VERSIONS_ENV in str(caught[0].message)

    def test_it_can_be_silenced(self):
        # Deployments that have made the decision and cannot move should not
        # have to read about it forever.
        snmpEngine = engine.SnmpEngine()

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            warnings.simplefilter("ignore", error.PySnmpWeakCryptoWarning)

            config.addV1System(snmpEngine, "my-area", "public")

    def test_adding_a_v3_user_does_not_warn(self, recwarn):
        snmpEngine = engine.SnmpEngine()
        config.addV3User(
            snmpEngine,
            "usr",
            config.usmHMACSHAAuthProtocol,
            "authkey1",
            config.usmAesCfb128Protocol,
            "privkey1",
        )

        assert [
            w for w in recwarn if issubclass(w.category, error.PySnmpWeakCryptoWarning)
        ] == []
