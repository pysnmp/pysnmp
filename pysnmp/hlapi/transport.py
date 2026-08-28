#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
from __future__ import annotations

from typing import Any

from pyasn1.compat.octets import null

from pysnmp import error
from pysnmp.carrier.base import AbstractTransport

__all__ = []


class AbstractTransportTarget:
    transportDomain: Any = None
    protoTransport: Any = AbstractTransport

    def __init__(
        self,
        transportAddr: tuple[str, ...],
        timeout: int = 1,
        retries: int = 5,
        tagList: Any = null,
    ) -> None:
        self.transportAddr = self._resolveAddr(transportAddr)
        self.timeout = timeout
        self.retries = retries
        self.tagList = tagList
        self.iface = None
        self.transport = None

    def __repr__(self) -> str:
        return '{}({!r}, timeout={!r}, retries={!r}, tagList={!r})'.format(
            self.__class__.__name__, self.transportAddr, self.timeout, self.retries, self.tagList
        )

    def getTransportInfo(self) -> tuple[Any, tuple[str, ...]]:
        return self.transportDomain, self.transportAddr

    def setLocalAddress(self, iface: tuple[str, ...] | None) -> AbstractTransportTarget:
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
        if not self.protoTransport.isCompatibleWithDispatcher(snmpEngine.transportDispatcher):
            raise error.PySnmpError(
                'Transport {!r} is not compatible with dispatcher {!r}'.format(
                    self.protoTransport, snmpEngine.transportDispatcher
                )
            )

    def _resolveAddr(self, transportAddr: tuple[str, ...]) -> tuple[str, ...]:
        raise NotImplementedError()
