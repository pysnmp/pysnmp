#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

"""Error indications: what went wrong, as values rather than status codes.

An error indication is a local failure -- no response, wrong digest, unknown
user -- as distinct from an error status, which is what a remote agent put in
a response it did send.
"""

import functools


@functools.total_ordering
class ErrorIndication(Exception):
    """SNMPv3 error-indication values."""

    def __init__(self, descr=None):
        """The value is the class name with a lowercase first letter.

        That is what makes an instance compare equal to the string the engine passes
        around, so a caller can test against either. `descr` changes what is printed
        without changing what it compares as.
        """
        self.__value = self.__descr = (
            self.__class__.__name__[0].lower() + self.__class__.__name__[1:]
        )
        if descr:
            self.__descr = descr

    def __eq__(self, other):
        return self.__value == other

    def __lt__(self, other):
        return self.__value < other

    def __str__(self):
        return self.__descr


# SNMP message processing errors


class SerializationError(ErrorIndication):
    """The message could not be encoded."""

    pass


serializationError = SerializationError("SNMP message serialization error")


class DeserializationError(ErrorIndication):
    """The message could not be decoded."""

    pass


deserializationError = DeserializationError("SNMP message deserialization error")


class ParseError(DeserializationError):
    """The message is not well-formed ASN.1."""

    pass


parseError = ParseError("SNMP message deserialization error")


class UnsupportedMsgProcessingModel(ErrorIndication):
    """The message names a version this engine has no processing model for."""

    pass


unsupportedMsgProcessingModel = UnsupportedMsgProcessingModel(
    "Unknown SNMP message processing model ID encountered"
)


class UnknownPDUHandler(ErrorIndication):
    """No application is registered for this PDU type."""

    pass


unknownPDUHandler = UnknownPDUHandler("Unhandled PDU type encountered")


class UnsupportedPDUtype(ErrorIndication):
    """The PDU type is not one this version defines."""

    pass


unsupportedPDUtype = UnsupportedPDUtype("Unsupported SNMP PDU type encountered")


class RequestTimedOut(ErrorIndication):
    """No response arrived before the last retry ran out."""

    pass


requestTimedOut = RequestTimedOut("No SNMP response received before timeout")


class EmptyResponse(ErrorIndication):
    """The response carried no PDU."""

    pass


emptyResponse = EmptyResponse("Empty SNMP response message")


class NonReportable(ErrorIndication):
    """The failure could not be reported back, so no report was sent."""

    pass


nonReportable = NonReportable("Report PDU generation not attempted")


class DataMismatch(ErrorIndication):
    """The response does not match the request it answers."""

    pass


dataMismatch = DataMismatch("SNMP request/response parameters mismatched")


class EngineIDMismatch(ErrorIndication):
    """The response came from a different engine than the request went to."""

    pass


engineIDMismatch = EngineIDMismatch("SNMP engine ID mismatch encountered")


class UnknownEngineID(ErrorIndication):
    """The engine ID is not one this engine knows."""

    pass


unknownEngineID = UnknownEngineID("Unknown SNMP engine ID encountered")


class TooBig(ErrorIndication):
    """The response would exceed what the transport can carry."""

    pass


tooBig = TooBig("SNMP message will be too big")


class LoopTerminated(ErrorIndication):
    """A walk was stopped because it was not making progress."""

    pass


loopTerminated = LoopTerminated("Infinite SNMP entities talk terminated")


class InvalidMsg(ErrorIndication):
    """The message header is malformed or self-inconsistent."""

    pass


invalidMsg = InvalidMsg("Invalid SNMP message header parameters encountered")


# SNMP security modules errors


class UnknownCommunityName(ErrorIndication):
    """The community string is not one this engine is configured for."""

    pass


unknownCommunityName = UnknownCommunityName("Unknown SNMP community name encountered")


class NoEncryption(ErrorIndication):
    """Privacy was asked for, but no privacy protocol is configured."""

    pass


noEncryption = NoEncryption("No encryption services configured")


class EncryptionError(ErrorIndication):
    """The message could not be encrypted."""

    pass


encryptionError = EncryptionError("Ciphering services not available")


class DecryptionError(ErrorIndication):
    """The message could not be decrypted, or the ciphertext is damaged."""

    pass


decryptionError = DecryptionError(
    "Ciphering services not available or ciphertext is broken"
)


class NoAuthentication(ErrorIndication):
    """Authentication was asked for, but no protocol is configured."""

    pass


noAuthentication = NoAuthentication("No authentication services configured")


class AuthenticationError(ErrorIndication):
    """The message could not be authenticated."""

    pass


authenticationError = AuthenticationError(
    "Ciphering services not available or bad parameters"
)


class AuthenticationFailure(ErrorIndication):
    """The digest does not match, so the message was altered or the key is wrong."""

    pass


authenticationFailure = AuthenticationFailure("Authenticator mismatched")


class UnsupportedAuthProtocol(ErrorIndication):
    """The authentication protocol is not one this build supports."""

    pass


unsupportedAuthProtocol = UnsupportedAuthProtocol(
    "Authentication protocol is not supprted"
)


class UnsupportedPrivProtocol(ErrorIndication):
    """The privacy protocol is not one this build supports."""

    pass


unsupportedPrivProtocol = UnsupportedPrivProtocol("Privacy protocol is not supprted")


class UnknownSecurityName(ErrorIndication):
    """The security name is not one this engine is configured for."""

    pass


unknownSecurityName = UnknownSecurityName("Unknown SNMP security name encountered")


class UnsupportedSecurityModel(ErrorIndication):
    """The message names a security model this engine does not have."""

    pass


unsupportedSecurityModel = UnsupportedSecurityModel("Unsupported SNMP security model")


class UnsupportedSecurityLevel(ErrorIndication):
    """The security level asked for is not one this engine can provide."""

    pass


# backward compatibility plug
UnsupportedSecLevel = UnsupportedSecurityLevel

unsupportedSecurityLevel = UnsupportedSecurityLevel("Unsupported SNMP security level")


class NotInTimeWindow(ErrorIndication):
    """The message's timestamp is outside the window this engine will accept.

    What SNMPv3 uses instead of a nonce: a message too far from the remote
    engine's clock is a replay, and is refused.
    """

    pass


notInTimeWindow = NotInTimeWindow(
    "SNMP message timing parameters not in windows of trust"
)


class UnknownUserName(ErrorIndication):
    """The USM user is not one this engine is configured for."""

    pass


unknownUserName = UnknownUserName("Unknown USM user")


class WrongDigest(ErrorIndication):
    """The PDU's digest does not match what was computed for it."""

    pass


wrongDigest = WrongDigest("Wrong SNMP PDU digest")


class ReportPduReceived(ErrorIndication):
    """The remote engine sent a report instead of a response.

    Carries the report's own counter, which is what says why.
    """

    pass


reportPduReceived = ReportPduReceived("Remote SNMP engine reported error")


# SNMP access-control errors


class NoSuchView(ErrorIndication):
    """The MIB view named does not exist."""

    pass


noSuchView = NoSuchView("No such MIB view currently exists")


class NoAccessEntry(ErrorIndication):
    """No access entry matches this group, context and security level."""

    pass


noAccessEntry = NoAccessEntry("Access to MIB node denined")


class NoGroupName(ErrorIndication):
    """No VACM group is configured for this security name."""

    pass


noGroupName = NoGroupName("No such VACM group configured")


class NoSuchContext(ErrorIndication):
    """The context named does not exist."""

    pass


noSuchContext = NoSuchContext("SNMP context now found")


class NotInView(ErrorIndication):
    """The OID is outside the view this request is allowed to see."""

    pass


notInView = NotInView("Requested OID is out of MIB view")


class AccessAllowed(ErrorIndication):
    """Not an error: access control allowed the operation."""

    pass


accessAllowed = AccessAllowed()


class OtherError(ErrorIndication):
    """Something else went wrong inside the engine."""

    pass


otherError = OtherError("Unspecified SNMP engine error occurred")


# SNMP Apps errors


class OidNotIncreasing(ErrorIndication):
    """The agent returned an OID no greater than the one asked about.

    A walk driven off such a response would never end, so it stops here.
    """

    pass


oidNotIncreasing = OidNotIncreasing("OID not increasing")
