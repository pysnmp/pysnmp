Receiving on a caller-bound socket
==================================

``UdpTransport.openServerMode(sock=sock)`` adopts an existing datagram socket.
This lets an agent bind a privileged port before dropping privileges, accept a
socket inherited from a service manager, or set socket options before binding.
The socket must have the transport's address family and ``SOCK_DGRAM`` type.
Pass either ``iface`` or ``sock``, never both.

For example, on POSIX, prepare the socket and then permanently switch to a
configured service account before constructing the SNMP engine::

    import asyncio
    import os
    import pwd
    import socket

    from pysnmp.carrier.asyncio.dgram import udp
    from pysnmp.entity import config, engine

    account = pwd.getpwnam("snmp-agent")  # an existing unprivileged account
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 161))

    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    snmpEngine = engine.SnmpEngine()
    transport = udp.UdpTransport(loop=loop).openServerMode(sock=sock)
    config.addTransport(snmpEngine, udp.domainName, transport)

Continue with authentication, access control and command responder setup as in
:doc:`the agent examples </examples/v3arch/asyncio/agent/cmdrsp/snmp-versions>`.
The example binds loopback only; choose the interface appropriate for the agent.
It requires an existing service account and starts with permission to bind the
port and switch identities. Failure to bind or change identity must abort startup.

Once the endpoint has opened successfully, asyncio owns the supplied socket.
Do not use or close it independently: closing the transport or the engine's
dispatcher closes it. Validation errors leave ownership with the caller. If
opening is scheduled on an already running event loop, wait for endpoint setup
before treating it as open, as with an address-bound transport.

For socket activation, wrap the inherited descriptor with ``socket.socket`` and
pass that socket instead of binding a new one. The transport takes ownership of
that descriptor too; duplicate it first if another component must retain its own
reference. The IPv6 datagram transport accepts sockets of its family through the same
API.
