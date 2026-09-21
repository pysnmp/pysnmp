"""Serving a request from instrumentation that has to be waited on.

An agent whose values come from a database, a REST call or another device
cannot produce them without waiting. These cover the path that lets it: an
instrumentation controller whose operations are coroutines, awaited by the
command responder while the engine goes on serving other requests.

The synchronous contract is unchanged and is what nearly every agent uses, so
it is covered here too -- specifically, that it never reaches the deferred path
at all.
"""

import asyncio
import socket

import pytest

import pysnmp.smi.error
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.carrier.base import AbstractTransportDispatcher
from pysnmp.carrier.error import CarrierError
from pysnmp.entity import config, engine
from pysnmp.entity.observer import execution_context
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.hlapi.asyncio import bulk_cmd, get_cmd, next_cmd, set_cmd
from pysnmp.hlapi.asyncio.transport import UdpTransportTarget
from pysnmp.hlapi.auth import CommunityData
from pysnmp.hlapi.context import ContextData
from pysnmp.proto import rfc1902
from pysnmp.smi import exval
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

REQUEST_EXECPOINT = "rfc3412.receiveMessage:request"

# Three consecutive objects under one prefix, so a walk has somewhere to go.
# Under an enterprise arc no MIB this side has loaded, so what comes back is
# taken at face value rather than cast to the syntax some real object declares.
FIRST = (1, 3, 6, 1, 4, 1, 20408, 999, 1, 0)
SECOND = (1, 3, 6, 1, 4, 1, 20408, 999, 2, 0)
THIRD = (1, 3, 6, 1, 4, 1, 20408, 999, 3, 0)
ORDERED = (FIRST, SECOND, THIRD)


def freePort() -> int:
    """A loopback UDP port nothing is bound to, as far as the OS knows."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def dotted(oid) -> str:
    """An OID as the dotted string both sides print it as."""
    return ".".join(str(sub) for sub in oid)


def securityNameOf(snmpEngine) -> str:
    """Who the request being served came from, as the engine resolved it.

    This is what a controller serving different values to different requesters
    reads, and reading it is only meaningful while the request it belongs to is
    the one being served.
    """
    securityName = snmpEngine.observer.getExecutionContext(REQUEST_EXECPOINT)[
        "securityName"
    ]
    return securityName.prettyPrint()


class AwaitingInstrum:
    """A controller that has to wait before it can answer.

    Every operation suspends at least once, which is the point: it is what a
    controller reading from somewhere else does, and what the responder has to
    cope with. Set `held` to a list and each operation waits there to be let go
    by name instead, which is how two requests are made to be in flight at the
    same time and finished in whichever order the test wants.
    """

    def __init__(self, values=None, byIdentity=None):
        self.values = dict(values or {})
        self.byIdentity = byIdentity or {}
        self.calls = 0
        self.held = None
        self.arrived = asyncio.Event()

    async def _pause(self):
        self.calls += 1

        if self.held is None:
            await asyncio.sleep(0)
            return

        gate = asyncio.Event()
        self.held.append(gate)
        self.arrived.set()
        await gate.wait()

    async def waitForHeld(self, count, timeout=10):
        """Wait until this many operations are suspended, all at once."""

        async def held():
            while len(self.held) < count:
                self.arrived.clear()
                if len(self.held) >= count:
                    break
                await self.arrived.wait()

        await asyncio.wait_for(held(), timeout)

    def _value(self, snmpEngine, oid):
        if self.byIdentity:
            return rfc1902.OctetString(self.byIdentity[securityNameOf(snmpEngine)])
        return self.values[oid]

    async def readVars(self, varBinds, **context):
        snmpEngine = context["acCtx"]
        await self._pause()
        return [
            (oid, self._value(snmpEngine, tuple(oid)))
            if tuple(oid) in self.values or self.byIdentity
            else (oid, exval.noSuchInstance)
            for oid, _ in varBinds
        ]

    async def readNextVars(self, varBinds, **context):
        snmpEngine = context["acCtx"]
        await self._pause()
        result = []
        for oid, _ in varBinds:
            following = next((o for o in ORDERED if o > tuple(oid)), None)
            if following is None:
                result.append((oid, exval.endOfMibView))
            else:
                result.append(
                    (rfc1902.ObjectName(following), self._value(snmpEngine, following))
                )
        return result

    async def writeVars(self, varBinds, **context):
        await self._pause()
        for oid, val in varBinds:
            self.values[tuple(oid)] = val
        return list(varBinds)


class SyncInstrum:
    """The ordinary controller: it has the answer already."""

    def __init__(self, values):
        self.values = dict(values)

    def readVars(self, varBinds, **context):
        return [(oid, self.values[tuple(oid)]) for oid, _ in varBinds]

    def readNextVars(self, varBinds, **context):
        result = []
        for oid, _ in varBinds:
            following = next((o for o in ORDERED if o > tuple(oid)), None)
            if following is None:
                result.append((oid, exval.endOfMibView))
            else:
                result.append((rfc1902.ObjectName(following), self.values[following]))
        return result

    def writeVars(self, varBinds, **context):
        return list(varBinds)


class FailingInstrum:
    """A controller that discovers, after suspending, that it cannot answer."""

    async def readVars(self, varBinds, **context):
        await asyncio.sleep(0)
        raise pysnmp.smi.error.GenError(idx=0)

    readNextVars = readVars
    writeVars = readVars


def startAgent(mibInstrum, communities=(("public", "area"),)):
    """An agent on a free loopback port, serving from `mibInstrum`."""
    port = freePort()

    agent = engine.SnmpEngine()
    config.addTransport(
        agent,
        udp.domainName + (1,),
        udp.UdpTransport().openServerMode(("127.0.0.1", port)),
    )

    for community, securityName in communities:
        config.addV1System(agent, securityName, community)
        config.addVacmUser(agent, 2, securityName, "noAuthNoPriv", (1, 3, 6, 1))

    snmpContext = context.SnmpContext(agent)
    snmpContext.contextNames[b""] = mibInstrum

    cmdrsp.GetCommandResponder(agent, snmpContext)
    cmdrsp.NextCommandResponder(agent, snmpContext)
    cmdrsp.BulkCommandResponder(agent, snmpContext)
    cmdrsp.SetCommandResponder(agent, snmpContext)

    return agent, port


def target(port):
    """Where the agent under test is, with little patience for a lost packet."""
    return UdpTransportTarget(("127.0.0.1", port), timeout=5, retries=1)


@pytest.fixture
async def agents():
    """Start agents for one test and close them, however the test ends.

    Asynchronous rather than plain, because what it hands back belongs to the
    loop it was built on: AsyncioDispatcher takes `get_running_loop()` when
    there is one and quietly makes a loop when there is not
    (pysnmp/carrier/asyncio/dispatch.py), so an agent built by a synchronous
    fixture would be attached to a loop no test ever runs. Closing here rather
    than in each test's `finally` also releases the sockets when an assertion
    fails before the close would have been reached.
    """
    started = []

    def start(mibInstrum, communities=(("public", "area"),)):
        agent, port = startAgent(mibInstrum, communities)
        started.append(agent)
        return agent, port

    yield start

    for agent in started:
        agent.closeDispatcher()


@pytest.fixture
async def manager():
    """A manager engine, closed however the test ends.

    `SnmpEngine.closeDispatcher()` rather than reaching through to the
    dispatcher: it tolerates a test that failed before the first request built
    one, and it detaches what it closed instead of leaving the engine holding a
    dispatcher that is already shut.
    """
    snmpEngine = engine.SnmpEngine()

    yield snmpEngine

    snmpEngine.closeDispatcher()


# --- the deferred path ------------------------------------------------------


async def test_get_waits_for_instrumentation_that_suspends(agents, manager):
    values = {FIRST: rfc1902.OctetString("served after waiting")}
    _, port = agents(AwaitingInstrum(values))
    errorIndication, errorStatus, _, varBinds = await get_cmd(
        manager,
        CommunityData("public", mpModel=1),
        target(port),
        ContextData(),
        ObjectType(ObjectIdentity(FIRST)),
    )
    assert errorIndication is None
    assert not errorStatus
    assert varBinds[0][1].prettyPrint() == "served after waiting"


async def test_getnext_waits_for_instrumentation_that_suspends(agents, manager):
    values = {oid: rfc1902.OctetString(f"value {i}") for i, oid in enumerate(ORDERED)}
    _, port = agents(AwaitingInstrum(values))
    errorIndication, errorStatus, _, varBinds = await next_cmd(
        manager,
        CommunityData("public", mpModel=1),
        target(port),
        ContextData(),
        ObjectType(ObjectIdentity(FIRST)),
    )
    assert errorIndication is None
    assert not errorStatus

    # One GETNEXT, so one row of one binding.
    oid, value = varBinds[0][0]
    assert str(oid) == dotted(SECOND)
    assert value.prettyPrint() == "value 1"


@pytest.mark.parametrize("nonRepeaters", [0, 1])
async def test_getbulk_waits_for_instrumentation_that_suspends(
    nonRepeaters, agents, manager
):
    """Both hand-off points: the non-repeaters, and a repetition after them.

    With no non-repeaters the first read to suspend is a repetition, and where
    the walk carries on from is only known once it comes back. With one, the
    read that suspends is the non-repeaters and the next input is already
    settled. The two enter the deferred path differently and both have to land
    on the same bindings.
    """
    values = {oid: rfc1902.OctetString(f"value {i}") for i, oid in enumerate(ORDERED)}
    _, port = agents(AwaitingInstrum(values))
    varBindsAsked = [ObjectType(ObjectIdentity(FIRST))]
    if nonRepeaters:
        varBindsAsked.insert(0, ObjectType(ObjectIdentity(FIRST)))

    errorIndication, errorStatus, _, varBinds = await bulk_cmd(
        manager,
        CommunityData("public", mpModel=1),
        target(port),
        ContextData(),
        nonRepeaters,
        3,
        *varBindsAsked,
    )
    assert errorIndication is None
    assert not errorStatus

    # One row per repetition; the repeating column is the one that walks.
    walked = [str(row[nonRepeaters][0]) for row in varBinds]
    assert walked == [dotted(SECOND), dotted(THIRD), dotted(THIRD)]

    if nonRepeaters:
        # The read that suspended, carried unchanged across every row.
        assert {str(row[0][0]) for row in varBinds} == {dotted(SECOND)}


async def test_set_waits_for_instrumentation_that_suspends(agents, manager):
    mibInstrum = AwaitingInstrum({FIRST: rfc1902.OctetString("before")})
    _, port = agents(mibInstrum)
    errorIndication, errorStatus, _, varBinds = await set_cmd(
        manager,
        CommunityData("public", mpModel=1),
        target(port),
        ContextData(),
        ObjectType(ObjectIdentity(FIRST), rfc1902.OctetString("after")),
    )
    assert errorIndication is None
    assert not errorStatus
    assert varBinds[0][1].prettyPrint() == "after"
    assert mibInstrum.values[FIRST].prettyPrint() == "after"


async def test_failure_after_suspending_is_still_an_error_status(agents, manager):
    """A controller that fails once suspended is answered, not left to time out."""
    _, port = agents(FailingInstrum())
    errorIndication, errorStatus, errorIndex, _ = await get_cmd(
        manager,
        CommunityData("public", mpModel=1),
        target(port),
        ContextData(),
        ObjectType(ObjectIdentity(FIRST)),
    )
    assert errorIndication is None
    assert errorStatus.prettyPrint() == "genErr"
    assert errorIndex == 1


async def test_a_suspended_request_does_not_take_the_next_ones_identity(
    agents, manager
):
    """The hazard the whole deferred path turns on.

    While one request waits, the engine serves another, which reaches the same
    execution point and records its own requester there. If that store were
    shared, the first request would resume and read the second's identity --
    and an agent that serves different values to different communities would
    answer one requester with another's data.
    """
    mibInstrum = AwaitingInstrum(byIdentity={"area": "for area", "other": "for other"})
    mibInstrum.held = []

    _, port = agents(mibInstrum, communities=(("public", "area"), ("secret", "other")))

    def ask(community):
        return asyncio.ensure_future(
            get_cmd(
                manager,
                CommunityData(community, mpModel=1),
                target(port),
                ContextData(),
                ObjectType(ObjectIdentity(FIRST)),
            )
        )

    # Both are held at once and on purpose: the second has to have reached
    # the execution point, and still be there, when the first looks at it
    # again.
    first = ask("public")
    await mibInstrum.waitForHeld(1)

    second = ask("secret")
    await mibInstrum.waitForHeld(2)

    mibInstrum.held[0].set()
    firstResult = await asyncio.wait_for(first, timeout=10)

    mibInstrum.held[1].set()
    secondResult = await asyncio.wait_for(second, timeout=10)

    assert firstResult[3][0][1].prettyPrint() == "for area"
    assert secondResult[3][0][1].prettyPrint() == "for other"


@pytest.mark.parametrize("controller", ["synchronous", "awaiting"])
async def test_a_request_reaches_its_execution_point_once(controller, agents, manager):
    """However the controller serves it.

    An observer at this point is how an application counts requests or logs
    who asked for what. Work that suspends is finished off the stack it
    started on and needs the point's state around it again -- but it reached
    the point once, so it is put back rather than entered again. Told twice,
    an observer would count the slow requests double and the rest single.
    """
    values = {oid: rfc1902.OctetString(f"value {i}") for i, oid in enumerate(ORDERED)}
    mibInstrum = (
        SyncInstrum(values) if controller == "synchronous" else AwaitingInstrum(values)
    )

    agent, port = agents(mibInstrum)
    reached = []
    agent.observer.registerObserver(
        lambda snmpEngine, execpoint, variables, cbCtx: reached.append(
            variables["securityName"]
        ),
        REQUEST_EXECPOINT,
    )

    errorIndication, errorStatus, _, varBinds = await get_cmd(
        manager,
        CommunityData("public", mpModel=1),
        target(port),
        ContextData(),
        ObjectType(ObjectIdentity(FIRST)),
    )
    assert errorIndication is None
    assert not errorStatus
    assert varBinds[0][1].prettyPrint() == "value 0"

    assert len(reached) == 1


# --- the synchronous path is untouched --------------------------------------


async def test_a_synchronous_controller_never_defers(agents, manager):
    """The ordinary agent answers on the stack it was asked on, as it always did."""
    values = {oid: rfc1902.OctetString(f"value {i}") for i, oid in enumerate(ORDERED)}
    agent, port = agents(SyncInstrum(values))

    deferrals = []
    dispatcher = agent.transportDispatcher
    runDeferred = dispatcher.runDeferred

    def recordingRunDeferred(coro, jobId=None):
        deferrals.append(coro)
        return runDeferred(coro, jobId)

    dispatcher.runDeferred = recordingRunDeferred

    errorIndication, errorStatus, _, varBinds = await get_cmd(
        manager,
        CommunityData("public", mpModel=1),
        target(port),
        ContextData(),
        ObjectType(ObjectIdentity(FIRST)),
    )
    assert errorIndication is None
    assert not errorStatus
    assert varBinds[0][1].prettyPrint() == "value 0"
    assert deferrals == []


# --- the pieces underneath --------------------------------------------------


async def test_execution_points_are_not_shared_between_tasks():
    snmpEngine = engine.SnmpEngine()
    started = asyncio.Event()
    release = asyncio.Event()

    async def holdOpen(name):
        with execution_context(snmpEngine, REQUEST_EXECPOINT, {"securityName": name}):
            started.set()
            await release.wait()
            return snmpEngine.observer.getExecutionContext(REQUEST_EXECPOINT)[
                "securityName"
            ]

    holder = asyncio.ensure_future(holdOpen("first"))
    await asyncio.wait_for(started.wait(), timeout=10)

    with execution_context(snmpEngine, REQUEST_EXECPOINT, {"securityName": "second"}):
        assert (
            snmpEngine.observer.getExecutionContext(REQUEST_EXECPOINT)["securityName"]
            == "second"
        )

    release.set()
    assert await holder == "first"


def test_execution_points_still_nest_within_one_task():
    snmpEngine = engine.SnmpEngine()
    observerOf = snmpEngine.observer

    with pytest.raises(KeyError):
        observerOf.getExecutionContext(REQUEST_EXECPOINT)

    with execution_context(snmpEngine, REQUEST_EXECPOINT, {"securityName": "outer"}):
        with execution_context(
            snmpEngine, REQUEST_EXECPOINT, {"securityName": "inner"}
        ):
            assert (
                observerOf.getExecutionContext(REQUEST_EXECPOINT)["securityName"]
                == "inner"
            )
        assert (
            observerOf.getExecutionContext(REQUEST_EXECPOINT)["securityName"] == "outer"
        )

    with pytest.raises(KeyError):
        observerOf.getExecutionContext(REQUEST_EXECPOINT)


def test_a_dispatcher_that_cannot_run_tasks_says_so():
    """Rather than dropping the work and leaving the requester to time out."""

    async def work():
        pass  # pragma: no cover - never started

    coro = work()
    try:
        with pytest.raises(CarrierError, match="may not be a coroutine"):
            AbstractTransportDispatcher().runDeferred(coro)
    finally:
        coro.close()


async def test_deferred_work_counts_as_outstanding_while_it_runs(agents):
    """So a dispatcher told to run until its work is done waits for the answer."""
    agent, port = agents(SyncInstrum({}))
    dispatcher = agent.transportDispatcher
    running = asyncio.Event()
    release = asyncio.Event()

    async def work():
        running.set()
        await release.wait()

    assert not dispatcher.jobsArePending()

    task = dispatcher.runDeferred(work())
    await asyncio.wait_for(running.wait(), timeout=10)
    assert dispatcher.jobsArePending()

    release.set()
    await asyncio.wait_for(task, timeout=10)
    assert not dispatcher.jobsArePending()


async def test_closing_the_dispatcher_drops_work_still_in_flight(agents):
    agent, port = agents(SyncInstrum({}))
    dispatcher = agent.transportDispatcher
    running = asyncio.Event()

    async def work():
        running.set()
        await asyncio.Event().wait()  # never set

    task = dispatcher.runDeferred(work())
    await asyncio.wait_for(running.wait(), timeout=10)

    await asyncio.wait_for(dispatcher.closeDispatcherAsync(), timeout=10)

    assert task.cancelled()
    assert not dispatcher.jobsArePending()
