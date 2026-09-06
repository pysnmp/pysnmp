#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#

from typing import Any, Generic, TypeVar

from pysnmp import error
from pysnmp.carrier.base import AbstractTransport

__all__ = []

#: The address shape a concrete target speaks. Each transport has its own --
#: (host, port) for UDP over IPv4 and IPv6, a path string for Unix domain
#: sockets -- so the base cannot name one and have the subclasses honour it.
_TransportAddr = TypeVar("_TransportAddr")


class AbstractTransportTarget(Generic[_TransportAddr]):
    transportDomain: Any = None
    protoTransport: Any = AbstractTransport

    def __init__(
        self,
        transportAddr: _TransportAddr,
        timeout: int = 1,
        retries: int = 5,
        tagList: Any = b"",
    ) -> None:
        self.transportAddr = self._resolveAddr(transportAddr)
        self.timeout = timeout
        self.retries = retries
        self.tagList = tagList
        self.iface: tuple[str, ...] | None = None
        self.transport: Any = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.transportAddr!r}, timeout={self.timeout!r}, retries={self.retries!r}, tagList={self.tagList!r})"

    def getTransportInfo(self) -> tuple[Any, _TransportAddr]:
        return self.transportDomain, self.transportAddr

    def setLocalAddress(
        self, iface: tuple[str, ...] | None
    ) -> "AbstractTransportTarget[_TransportAddr]":
        """Set source address.

        Parameters
        ----------
        iface : tuple
            Indicates network address of a local interface from which SNMP packets will be originated.
            Format is the same as of `transportAddress`.

        Returns
        -------
            self

        """
        self.iface = iface
        return self

    def openClientMode(self) -> Any:
        self.transport = self.protoTransport().openClientMode(self.iface)
        return self.transport

    def verifyDispatcherCompatibility(self, snmpEngine: Any) -> None:
        if not self.protoTransport.isCompatibleWithDispatcher(
            snmpEngine.transportDispatcher
        ):
            raise error.PySnmpError(
                f"Transport {self.protoTransport!r} is not compatible with dispatcher {snmpEngine.transportDispatcher!r}"
            )

    def _resolveAddr(self, transportAddr: _TransportAddr) -> _TransportAddr:
        raise NotImplementedError()
