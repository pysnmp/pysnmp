Device details report
=====================

The device-report helper collects the standard objects from the
``SNMPv2-MIB::system`` group and walks ``SNMPv2-MIB::sysORTable`` in one
operation. It returns a :class:`~pysnmp.hlapi.DeviceReport` containing:

* ``description`` (``sysDescr.0``)
* ``vendor_oid`` (``sysObjectID.0``)
* ``uptime`` (``sysUpTime.0``, in centiseconds)
* ``contact``, ``name``, ``location`` and ``services``
* ``implemented_mibs``, a list of :class:`~pysnmp.hlapi.SysOREntry` rows

Unavailable scalar objects are represented by ``None``. The table walk is
bounded to the four ``sysORTable`` columns, so objects following the table in
the agent's MIB view are never reported as capabilities.

Asynchronous use
----------------

The asyncio API returns the report directly from a coroutine:

.. literalinclude:: /../../examples/hlapi/asyncio/manager/cmdgen/device-report.py
   :language: python

:download:`Download the asyncio example
</../../examples/hlapi/asyncio/manager/cmdgen/device-report.py>`.

Synchronous use
---------------

The default :mod:`pysnmp.hlapi` facade provides the same operation as a
blocking function:

.. code-block:: python

   from pysnmp.hlapi import (
       CommunityData,
       ContextData,
       SnmpEngine,
       UdpTransportTarget,
       get_device_report,
   )

   report = get_device_report(
       SnmpEngine(),
       CommunityData("public"),
       UdpTransportTarget(("demo.pysnmp.com", 161)),
       ContextData(),
   )
   print(report.name, report.vendor_oid)

The helper uses GETNEXT for ``sysORTable`` so the same API works with SNMPv1,
SNMPv2c and SNMPv3 credentials. The legacy spelling ``getDeviceReport`` is
retained as an alias.

API reference
-------------

.. autofunction:: pysnmp.hlapi.asyncio.get_device_report

.. autoclass:: pysnmp.hlapi.DeviceReport
   :members:

.. autoclass:: pysnmp.hlapi.SysOREntry
   :members:
