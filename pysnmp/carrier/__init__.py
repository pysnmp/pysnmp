# This file is necessary to make this directory a package.
"""Transports: how an SNMP message reaches the network and comes back.

`base` states what a transport and a dispatcher have to do; `asyncio` is the
implementation the engine uses, over UDP, UDP/IPv6 and Unix domain sockets.
"""
