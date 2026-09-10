#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Building and reading SNMPv1 messages and PDUs."""

from pyasn1.type import univ

from pysnmp import nextid
from pysnmp.proto import error, rfc1155, rfc1157

# Shortcuts to SNMP types
Integer = univ.Integer
OctetString = univ.OctetString
Null = univ.Null
null = Null("")
ObjectIdentifier = univ.ObjectIdentifier

IpAddress = rfc1155.IpAddress
NetworkAddress = rfc1155.NetworkAddress
Counter = rfc1155.Counter
Gauge = rfc1155.Gauge
TimeTicks = rfc1155.TimeTicks
Opaque = rfc1155.Opaque

VarBind = rfc1157.VarBind
VarBindList = rfc1157.VarBindList
GetRequestPDU = rfc1157.GetRequestPDU
GetNextRequestPDU = rfc1157.GetNextRequestPDU
GetResponsePDU = rfc1157.GetResponsePDU
SetRequestPDU = rfc1157.SetRequestPDU
TrapPDU = rfc1157.TrapPDU
Message = rfc1157.Message


class VarBindAPI:
    """Reads and writes the two halves of a variable binding."""

    @staticmethod
    def setOIDVal(varBind, oidVal):
        """Set both halves of a binding, treating `None` as the v1 null value.

        The value goes in with tag and constraint checks off, because the binding's
        CHOICE is what decides the type and re-checking it here would reject a
        perfectly legal value that this API was handed deliberately.
        """
        oid, val = oidVal[0], oidVal[1]
        varBind.setComponentByPosition(0, oid)
        if val is None:
            val = null
        varBind.setComponentByPosition(1).getComponentByPosition(1).setComponentByType(
            val.tagSet,
            val,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
            innerFlag=True,
        )
        return varBind

    @staticmethod
    def getOIDVal(varBind):
        """The OID and the value, with the binding's CHOICE already unwrapped."""
        return varBind[0], varBind[1].getComponent(1)


apiVarBind = VarBindAPI()

getNextRequestID = nextid.Integer(0xFFFFFF)


class PDUAPI:
    """Reads and writes a v1 PDU without naming its fields directly."""

    _errorStatus = rfc1157.errorStatus.clone(0)
    _errorIndex = Integer(0)

    def setDefaults(self, pdu):
        """Stamp a fresh request ID and clear the error fields."""
        pdu.setComponentByPosition(
            0,
            getNextRequestID(),
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        pdu.setComponentByPosition(
            1,
            self._errorStatus,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        pdu.setComponentByPosition(
            2,
            self._errorIndex,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        varBindList = pdu.setComponentByPosition(3).getComponentByPosition(3)
        varBindList.clear()

    @staticmethod
    def getRequestID(pdu):
        """The request ID a response is matched back by."""
        return pdu.getComponentByPosition(0)

    @staticmethod
    def setRequestID(pdu, value):
        """Set the request ID."""
        pdu.setComponentByPosition(0, value)

    @staticmethod
    def getErrorStatus(pdu):
        """The error status, as the small integer set of :RFC:`1157#section-4.1`."""
        return pdu.getComponentByPosition(1)

    @staticmethod
    def setErrorStatus(pdu, value):
        """Set the error status."""
        pdu.setComponentByPosition(1, value)

    @staticmethod
    def getErrorIndex(pdu, muteErrors=False):
        """The 1-based binding the error refers to, checked against the bindings present.

        An index past the end of the list is a malformed response, and agents do send
        them. `muteErrors` clamps to the last binding instead of raising, for callers
        that would rather carry on with a peer that is not quite right.
        """
        errorIndex = pdu.getComponentByPosition(2)
        if errorIndex > len(pdu[3]):
            if muteErrors:
                return errorIndex.clone(len(pdu[3]))
            raise error.ProtocolError(
                f"Error index out of range: {errorIndex} > {len(pdu[3])}"
            )
        return errorIndex

    @staticmethod
    def setErrorIndex(pdu, value):
        """Set the error index."""
        pdu.setComponentByPosition(2, value)

    def setEndOfMibError(self, pdu, errorIndex):
        """Report the end of the MIB the only way v1 can, as `noSuchName`.

        v1 has no `endOfMibView`: running off the end of the tree and asking for an
        object that does not exist are the same answer, which is why a v1 walk has to
        stop on an error rather than on a value.
        """
        self.setErrorIndex(pdu, errorIndex)
        self.setErrorStatus(pdu, 2)

    def setNoSuchInstanceError(self, pdu, errorIndex):
        """Report a missing instance, which in v1 is `noSuchName` as well."""
        self.setEndOfMibError(pdu, errorIndex)

    @staticmethod
    def getVarBindList(pdu):
        """The binding list as the ASN.1 object, not as pairs."""
        return pdu.getComponentByPosition(3)

    @staticmethod
    def setVarBindList(pdu, varBindList):
        """Set the binding list from an ASN.1 object."""
        pdu.setComponentByPosition(3, varBindList)

    @staticmethod
    def getVarBinds(pdu):
        """The bindings as `(oid, value)` pairs."""
        return [
            apiVarBind.getOIDVal(varBind) for varBind in pdu.getComponentByPosition(3)
        ]

    @staticmethod
    def setVarBinds(pdu, varBinds):
        """Set the bindings from `(oid, value)` pairs, or from ASN.1 bindings."""
        varBindList = pdu.setComponentByPosition(3).getComponentByPosition(3)
        varBindList.clear()
        for idx, varBind in enumerate(varBinds):
            if isinstance(varBind, VarBind):
                varBindList.setComponentByPosition(idx, varBind)
            else:
                varBindList.setComponentByPosition(idx)
                apiVarBind.setOIDVal(varBindList.getComponentByPosition(idx), varBind)

    def getResponse(self, reqPDU):
        """An empty response PDU carrying the request's ID."""
        rspPDU = GetResponsePDU()
        self.setDefaults(rspPDU)
        self.setRequestID(rspPDU, self.getRequestID(reqPDU))
        return rspPDU

    def getVarBindTable(self, reqPDU, rspPDU):
        """The response's bindings as a table of one row.

        GETBULK is what makes this a table rather than a list, and v1 has no GETBULK,
        so the row count here is always one. A `noSuchName` response comes back as the
        requested OIDs paired with nulls, since v1 leaves the bindings of an error
        response unspecified and the caller still needs to know which OIDs ended.
        """
        if apiPDU.getErrorStatus(rspPDU) == 2:
            varBindRow = []
            for varBind in apiPDU.getVarBinds(reqPDU):
                varBindRow.append((varBind[0], null))
            return [varBindRow]
        else:
            return [apiPDU.getVarBinds(rspPDU)]


apiPDU = PDUAPI()


class TrapPDUAPI:
    """Reads and writes a v1 trap, whose fields are unlike any other PDU's."""

    _networkAddress = None
    _entOid = ObjectIdentifier((1, 3, 6, 1, 4, 1, 20408))
    _genericTrap = rfc1157.genericTrap.clone("coldStart")
    _zeroInt = univ.Integer(0)
    _zeroTime = TimeTicks(0)

    def setDefaults(self, pdu):
        """Fill in the trap fields, resolving this host's address once and caching it.

        A v1 trap states where it came from in a dedicated field, so the address has
        to be found before one can be built. Where the host cannot resolve its own
        name the unspecified address stands in, which :RFC:`1157` allows for an
        agent that does not know its own address.
        """
        if self._networkAddress is None:
            try:
                import socket

                agentAddress = IpAddress(socket.gethostbyname(socket.gethostname()))
            except Exception:  # noqa: BLE001 - resolving our own hostname is optional; the unspecified address is the documented fallback
                # :RFC:`1157` agent-addr with the address unknown.
                agentAddress = IpAddress("0.0.0.0")  # noqa: S104
            self._networkAddress = NetworkAddress().setComponentByPosition(
                0, agentAddress
            )
        pdu.setComponentByPosition(
            0,
            self._entOid,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        pdu.setComponentByPosition(
            1,
            self._networkAddress,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        pdu.setComponentByPosition(
            2,
            self._genericTrap,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        pdu.setComponentByPosition(
            3,
            self._zeroInt,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        pdu.setComponentByPosition(
            4,
            self._zeroTime,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        varBindList = pdu.setComponentByPosition(5).getComponentByPosition(5)
        varBindList.clear()

    @staticmethod
    def getEnterprise(pdu):
        """The OID naming what kind of device sent the trap."""
        return pdu.getComponentByPosition(0)

    @staticmethod
    def setEnterprise(pdu, value):
        """Set the enterprise OID."""
        pdu.setComponentByPosition(0, value)

    @staticmethod
    def getAgentAddr(pdu):
        """The IPv4 address the trap claims to come from."""
        return pdu.getComponentByPosition(1).getComponentByPosition(0)

    @staticmethod
    def setAgentAddr(pdu, value):
        """Set the agent address, which v1 can only express as IPv4."""
        pdu.setComponentByPosition(1).getComponentByPosition(1).setComponentByPosition(
            0, value
        )

    @staticmethod
    def getGenericTrap(pdu):
        """Which of the six predefined traps this is, or `enterpriseSpecific`."""
        return pdu.getComponentByPosition(2)

    @staticmethod
    def setGenericTrap(pdu, value):
        """Set the generic trap number."""
        pdu.setComponentByPosition(2, value)

    @staticmethod
    def getSpecificTrap(pdu):
        """The vendor's own trap number, meaningful only alongside the enterprise OID."""
        return pdu.getComponentByPosition(3)

    @staticmethod
    def setSpecificTrap(pdu, value):
        """Set the specific trap number."""
        pdu.setComponentByPosition(3, value)

    @staticmethod
    def getTimeStamp(pdu):
        """How long the sending agent had been up when the trap fired."""
        return pdu.getComponentByPosition(4)

    @staticmethod
    def setTimeStamp(pdu, value):
        """Set the uptime stamp."""
        pdu.setComponentByPosition(4, value)

    @staticmethod
    def getVarBindList(pdu):
        """The binding list as the ASN.1 object, not as pairs."""
        return pdu.getComponentByPosition(5)

    @staticmethod
    def setVarBindList(pdu, varBindList):
        """Set the binding list from an ASN.1 object."""
        pdu.setComponentByPosition(5, varBindList)

    @staticmethod
    def getVarBinds(pdu):
        """The bindings as `(oid, value)` pairs."""
        varBinds = []
        for varBind in pdu.getComponentByPosition(5):
            varBinds.append(apiVarBind.getOIDVal(varBind))
        return varBinds

    @staticmethod
    def setVarBinds(pdu, varBinds):
        """Set the bindings from `(oid, value)` pairs, or from ASN.1 bindings."""
        varBindList = pdu.setComponentByPosition(5).getComponentByPosition(5)
        varBindList.clear()
        for idx, varBind in enumerate(varBinds):
            if isinstance(varBind, VarBind):
                varBindList.setComponentByPosition(idx, varBind)
            else:
                varBindList.setComponentByPosition(idx)
                apiVarBind.setOIDVal(varBindList.getComponentByPosition(idx), varBind)


apiTrapPDU = TrapPDUAPI()


class MessageAPI:
    """Reads and writes a v1 message: version, community, and the PDU inside."""

    _version = rfc1157.version.clone(0)
    _community = univ.OctetString("public")

    def setDefaults(self, msg):
        """Stamp version 1 and the default community."""
        msg.setComponentByPosition(
            0,
            self._version,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        msg.setComponentByPosition(
            1,
            self._community,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
        )
        return msg

    @staticmethod
    def getVersion(msg):
        """The version field, which the dispatcher reads before anything else."""
        return msg.getComponentByPosition(0)

    @staticmethod
    def setVersion(msg, value):
        """Set the version field."""
        msg.setComponentByPosition(0, value)

    @staticmethod
    def getCommunity(msg):
        """The community, which in v1 is both the credential and the whole of the security."""
        return msg.getComponentByPosition(1)

    @staticmethod
    def setCommunity(msg, value):
        """Set the community."""
        msg.setComponentByPosition(1, value)

    @staticmethod
    def getPDU(msg):
        """The PDU carried inside the message."""
        return msg.getComponentByPosition(2).getComponent()

    @staticmethod
    def setPDU(msg, value):
        """Set the PDU carried inside the message."""
        msg.setComponentByPosition(2).getComponentByPosition(2).setComponentByType(
            value.tagSet,
            value,
            verifyConstraints=False,
            matchTags=False,
            matchConstraints=False,
            innerFlag=True,
        )

    def getResponse(self, reqMsg):
        """A response message echoing the request's version, community and request ID."""
        rspMsg = Message()
        self.setDefaults(rspMsg)
        self.setVersion(rspMsg, self.getVersion(reqMsg))
        self.setCommunity(rspMsg, self.getCommunity(reqMsg))
        self.setPDU(rspMsg, apiPDU.getResponse(self.getPDU(reqMsg)))
        return rspMsg


apiMessage = MessageAPI()
