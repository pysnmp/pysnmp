"""
Serving values the agent has to wait for
++++++++++++++++++++++++++++++++++++++++

Listen and respond to SNMP GET/GETNEXT/GETBULK/SET queries with the
following options:

* SNMPv2c, community 'public'
* serving objects from an instrumentation controller whose operations are
  coroutines, standing in for a database or a remote service
* allow access to objects under 1.3.6.1.4.1.20408
* over IPv4/UDP, listening at 127.0.0.1:1161

The controller waits before it can answer, and the engine goes on serving
other requests while it does -- so one slow object does not stall the agent.

Either of the following Net-SNMP commands will exercise this Agent:

| $ snmpget -v2c -c public 127.0.0.1:1161 1.3.6.1.4.1.20408.999.1.0
| $ snmpwalk -v2c -c public 127.0.0.1:1161 1.3.6.1.4.1.20408
| $ snmpbulkwalk -v2c -c public 127.0.0.1:1161 1.3.6.1.4.1.20408

"""  #

import asyncio

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.proto import rfc1902
from pysnmp.smi import exval

# The objects this agent serves, in the lexicographic order a walk needs.
OBJECTS = {
    (1, 3, 6, 1, 4, 1, 20408, 999, 1, 0): "the first value",
    (1, 3, 6, 1, 4, 1, 20408, 999, 2, 0): "the second value",
    (1, 3, 6, 1, 4, 1, 20408, 999, 3, 0): "the third value",
}


class SlowInstrum:
    """An instrumentation controller that has to wait for its values.

    The three operations are the whole contract; nothing has to be inherited.
    Declaring them `async def` is how a controller says it cannot answer
    without waiting, which is what an agent reading from a database, a REST
    service or another device is really doing.
    """

    async def _fetch(self, oid):
        """Stands in for the query that has to go somewhere and come back."""
        await asyncio.sleep(0.25)
        return rfc1902.OctetString(OBJECTS[oid])

    async def readVars(self, varBinds, **context):
        """Read exactly the objects named."""
        result = []
        for oid, _ in varBinds:
            name = tuple(oid)
            if name in OBJECTS:
                result.append((oid, await self._fetch(name)))
            else:
                result.append((oid, exval.noSuchInstance))
        return result

    async def readNextVars(self, varBinds, **context):
        """Read the objects following those named, which is what a walk asks for."""
        ordered = sorted(OBJECTS)
        result = []
        for oid, _ in varBinds:
            following = next((o for o in ordered if o > tuple(oid)), None)
            if following is None:
                result.append((oid, exval.endOfMibView))
            else:
                result.append(
                    (rfc1902.ObjectName(following), await self._fetch(following))
                )
        return result

    async def writeVars(self, varBinds, **context):
        """Refuse every write. Reads are what this agent is for."""
        return [(oid, exval.noSuchInstance) for oid, _ in varBinds]


async def main():
    """Serve requests until interrupted."""
    snmpEngine = engine.SnmpEngine()

    config.addTransport(
        snmpEngine,
        udp.domainName,
        udp.UdpTransport().openServerMode(("127.0.0.1", 1161)),
    )

    config.addV1System(snmpEngine, "my-area", "public")
    config.addVacmUser(
        snmpEngine, 2, "my-area", "noAuthNoPriv", (1, 3, 6, 1, 4, 1, 20408)
    )

    # A controller is whatever object is registered for the context, so this
    # one replaces the MIB-backed controller the context would have built.
    snmpContext = context.SnmpContext(snmpEngine)
    snmpContext.contextNames[b""] = SlowInstrum()

    cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.NextCommandResponder(snmpEngine, snmpContext)
    cmdrsp.BulkCommandResponder(snmpEngine, snmpContext)
    cmdrsp.SetCommandResponder(snmpEngine, snmpContext)

    try:
        await asyncio.Event().wait()
    finally:
        await snmpEngine.transportDispatcher.closeDispatcherAsync()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
