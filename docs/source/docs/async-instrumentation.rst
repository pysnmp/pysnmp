.. _async-instrumentation:

Serving values an agent has to wait for
=======================================

An agent that answers out of a loaded MIB has its values in memory already.
An agent that answers out of a database, a REST call, a subprocess or another
SNMP device does not: it has to wait for them. Until now that left two poor
options -- block the event loop and stall every other request in flight, or
run a thread pool and bridge back by hand.

An instrumentation controller may declare its operations ``async def``
instead. The command responder waits for the answer, and the engine goes on
serving other requests while it does.

A controller that waits
-----------------------

A controller is whatever object the command responder was given; nothing has
to be inherited. It provides three operations, matching the request types::

    from pysnmp.proto import rfc1902
    from pysnmp.smi import exval


    class DatabaseInstrum:
        """Serves managed objects out of a database."""

        def __init__(self, pool):
            self.pool = pool

        async def readVars(self, varBinds, **context):
            async with self.pool.acquire() as connection:
                return [
                    (oid, await self._read(connection, oid)) for oid, _ in varBinds
                ]

        async def readNextVars(self, varBinds, **context):
            async with self.pool.acquire() as connection:
                return [
                    await self._following(connection, oid) for oid, _ in varBinds
                ]

        async def writeVars(self, varBinds, **context):
            async with self.pool.acquire() as connection:
                for oid, value in varBinds:
                    await self._write(connection, oid, value)
                return list(varBinds)

Register it the way any controller is registered, against the context it
serves::

    snmpContext = context.SnmpContext(snmpEngine)
    snmpContext.contextNames[b''] = DatabaseInstrum(pool)

    cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.NextCommandResponder(snmpEngine, snmpContext)
    cmdrsp.BulkCommandResponder(snmpEngine, snmpContext)
    cmdrsp.SetCommandResponder(snmpEngine, snmpContext)

Nothing else changes. The same arguments arrive, the same bindings go back,
and an SMI error raised out of a coroutine becomes the same error status it
would have as a plain ``def`` -- including the two-phase behaviour a SET
relies on, since ``writeVars`` still either returns having committed
everything or raises having committed nothing.

The three may be mixed: a controller whose reads come from a database and
whose writes are refused outright can leave ``writeVars`` a plain function.

What stays true across the wait
-------------------------------

A request that suspends is still that request when it resumes. What a
controller reads from the engine while it runs -- notably the requester's
identity, at the ``rfc3412.receiveMessage:request`` execution point --
belongs to the request being served and is not disturbed by the ones that
arrive meanwhile::

    def securityNameOf(snmpEngine):
        execCtx = snmpEngine.observer.getExecutionContext(
            'rfc3412.receiveMessage:request'
        )
        return execCtx['securityName'].prettyPrint()

This matters for exactly the agents that need to wait. One serving different
values to different communities reads that identity to decide what to serve,
and reads it after the wait, not before. If the engine kept one execution
point for the whole process, a request that resumed after another had arrived
would read the other's identity and answer one requester with another's data.
Each request sees its own.

What this does not cover
------------------------

The managed objects inside ``MibInstrumController`` -- ``MibScalarInstance``
and the rest of the MIB tree -- are still plain functions. An agent that wants to wait implements the controller contract
above rather than plugging a coroutine into a loaded MIB tree.

Access control is not awaited either. The ``acFun`` callback resolves from
VACM's in-memory tables, so there is nothing behind it to wait for.

What it costs
-------------

Nothing, for an agent that does not use it. A controller whose operations are
plain functions answers on the stack it was asked on, exactly as before: no
task is created, no loop iteration is spent, and the code path is the one that
has always run. The deferred path is entered only when an operation actually
hands back something to wait on.

While a request is waiting, it counts as outstanding work on the transport
dispatcher, so ``runDispatcher()`` told to run until its work is done waits
for the answer rather than returning while it is still being composed. Closing the dispatcher cancels whatever is
still in flight: the transports its answer would leave by are being closed
underneath it.
