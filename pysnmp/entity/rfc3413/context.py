#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The SNMPv3 context: which engine and which named view a request applies to."""

from pyasn1.type import univ

from pysnmp import debug, error


class SnmpContext:
    """Maps a context name to the MIB instrumentation that serves it.

    A context is how one engine presents more than one set of managed objects --
    per VRF, per virtual router, per tenant. The empty name is the default
    context, which is what an agent with only one set of objects uses.
    """

    def __init__(self, snmpEngine, contextEngineId=None):
        """Defaults the context engine ID to the local engine's own."""
        (snmpEngineId,) = (
            snmpEngine.msgAndPduDsp.mibInstrumController.mibBuilder.importSymbols(
                "__SNMP-FRAMEWORK-MIB", "snmpEngineID"
            )
        )
        if contextEngineId is None:
            # Default to local snmpEngineId
            self.contextEngineId = snmpEngineId.syntax
        else:
            self.contextEngineId = snmpEngineId.syntax.clone(contextEngineId)
        debug.logger & debug.flagIns and debug.logger(
            f'SnmpContext: contextEngineId "{self.contextEngineId!r}"'
        )
        self.contextNames = {
            b"": snmpEngine.msgAndPduDsp.mibInstrumController
        }  # Default name

    def registerContextName(self, contextName, mibInstrum=None):
        """Serve a context name from an instrumentation, or from the default one.

        This is what lets one agent present different sets of objects under different
        context names, which v3 has and v1 and v2c reach only through the community.
        """
        contextName = univ.OctetString(contextName).asOctets()
        if contextName in self.contextNames:
            raise error.PySnmpError(f"Duplicate contextName {contextName}")
        debug.logger & debug.flagIns and debug.logger(
            f"registerContextName: registered contextName {contextName!r}, mibInstrum {mibInstrum!r}"
        )
        if mibInstrum is None:
            self.contextNames[contextName] = self.contextNames[b""]
        else:
            self.contextNames[contextName] = mibInstrum

    def unregisterContextName(self, contextName):
        """Stop serving a context name. Unknown names are ignored."""
        contextName = univ.OctetString(contextName).asOctets()
        if contextName in self.contextNames:
            debug.logger & debug.flagIns and debug.logger(
                f"unregisterContextName: unregistered contextName {contextName!r}"
            )
            del self.contextNames[contextName]

    def getMibInstrum(self, contextName=b""):
        """The instrumentation serving a context name. Raises where it is not registered."""
        contextName = univ.OctetString(contextName).asOctets()
        if contextName not in self.contextNames:
            debug.logger & debug.flagIns and debug.logger(
                f"getMibInstrum: contextName {contextName!r} not registered"
            )
            raise error.PySnmpError(f"Missing contextName {contextName}")
        else:
            debug.logger & debug.flagIns and debug.logger(
                f"getMibInstrum: contextName {contextName!r}, mibInstum {self.contextNames[contextName]!r}"
            )
            return self.contextNames[contextName]
