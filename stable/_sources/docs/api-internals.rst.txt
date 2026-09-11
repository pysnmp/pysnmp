Errors and supporting types
===========================

The objects on this page are referenced throughout the library reference and
the docstrings — as the exceptions an operation raises, the type a call hands
back, or the MIB services the high-level API is built on. They are collected
here so that every one of those references resolves.

Exceptions
----------

.. autoexception:: pysnmp.error.PySnmpError
   :members:

.. autoexception:: pysnmp.smi.error.SmiError
   :members:

   Raised by the SMI layer. It derives from both
   :exc:`~pysnmp.error.PySnmpError` and :class:`~pyasn1.error.PyAsn1Error`, so
   either is enough to catch it.

Warnings
--------

.. autoexception:: pysnmp.error.PySnmpCryptoWarning

.. autoexception:: pysnmp.error.PySnmpWeakCryptoWarning

.. autoexception:: pysnmp.error.PySnmpNonStandardCryptoWarning

Return types
------------

.. module:: pysnmp.hlapi

.. autoclass:: pysnmp.hlapi.types.SnmpResponse

.. autodata:: pysnmp.proto.rfc1905.endOfMibView
   :annotation:

   The value a response carries in place of a variable binding when a walk has
   run past the end of the MIB view.

.. autoclass:: pysnmp.proto.rfc1902.ObjectName

Transport
---------

.. py:class:: pysnmp.hlapi.transport.TransportAddrT

   The address shape a concrete transport target speaks. Each transport has
   its own -- a ``(host, port)`` pair for UDP over IPv4 and IPv6, a path
   string for Unix domain sockets -- so :py:class:`AbstractTransportTarget
   <pysnmp.hlapi.transport.AbstractTransportTarget>` is generic in it rather
   than naming one its subclasses would have to contradict.

.. autoclass:: pysnmp.hlapi.transport.AbstractTransportTarget
   :members:
   :exclude-members: protoTransport


MIB services
------------

.. module:: pysnmp.smi.rfc1902

.. autoclass:: pysnmp.smi.builder.MibBuilder
   :members: addMibSources, getMibSources, loadModules, importSymbols

.. autoclass:: pysnmp.smi.view.MibViewController
   :members:

Synchronous command generators
------------------------------

These are the blocking counterparts of the coroutines in
:doc:`hlapi/asyncio/manager/cmdgen/getcmd` and its siblings. They take the same
arguments and return the same tuple, having driven the event loop themselves.

.. autofunction:: pysnmp.hlapi.getCmd

.. autofunction:: pysnmp.hlapi.setCmd

.. autofunction:: pysnmp.hlapi.nextCmd

.. autofunction:: pysnmp.hlapi.bulkCmd
