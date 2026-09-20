
.. _breaking-changes:

Breaking Changes
================

This release is not backwards compatible with the 5.0 series. The changes
below require source modifications in applications that used the removed
interfaces. See :doc:`/changelog` for the complete list of changes.

MIB instrumentation takes ``(varBind, **context)``
---------------------------------------------------

The methods a managed object implements took ``(name, val, idx, acInfo)`` and
take ``(varBind, **context)`` now, where ``varBind`` is an
``(ObjectName, value)`` pair and ``context`` carries ``idx``, ``acFun`` and
``acCtx``:

.. code-block:: python

   # was
   class MyScalar(MibScalarInstance):
       def readGet(self, name, val, idx, acInfo):
           return name, self.syntax.clone(read_my_value())

   # now
   class MyScalar(MibScalarInstance):
       def readGet(self, varBind, **context):
           name, val = varBind
           return name, self.syntax.clone(read_my_value())

The same applies to the instrumentation contract one level up:
``readVars``/``readNextVars``/``writeVars`` took ``(varBinds, acInfo)`` and take
``(varBinds, **context)``.

**Nothing has been removed.** A class written the old way keeps serving requests
unmodified: PySNMP detects the old signature and adapts the call, emitting a
``DeprecationWarning`` that names the class and the methods it adapted. The
detection happens once per class, not per request, so a class on the current
signature pays nothing at all.

Why the shape changed: every piece of information a managed object might need
had to be another positional argument, and adding one broke every
implementation. A context mapping can carry what a given call needs without
changing the signature again -- including an awaitable, which is the
prerequisite for asynchronous instrumentation.

To find what needs changing, run with deprecation warnings visible::

    python -W error::DeprecationWarning your_agent.py

The names match `lextudio/pysnmp <https://github.com/lextudio/pysnmp>`_ and the
2018 upstream work both forks descend from, so an implementation written for
either ports across.

The high-level API is snake_case, and camelCase is deprecated
-------------------------------------------------------------

The high-level API followed camelCase, which PEP 8 does not call for. The
canonical spelling is snake_case now:

=============================  ============================
Was                            Now
=============================  ============================
``getCmd``                     ``get_cmd``
``nextCmd``                    ``next_cmd``
``setCmd``                     ``set_cmd``
``bulkCmd``                    ``bulk_cmd``
``isEndOfMib``                 ``is_end_of_mib``
``sendNotification``           ``send_notification``
``getDeviceReport``            ``get_device_report``
``dhKeyChange``                ``dh_key_change``
=============================  ============================

**Nothing has been removed.** Every old name still resolves to the same
function and behaves identically; using one emits a ``DeprecationWarning``
naming its replacement. Existing code keeps working untouched, so this is a
rename to migrate to at your own pace rather than a break to fix before
upgrading.

To find what needs changing, run with deprecation warnings visible::

    python -W error::DeprecationWarning your_app.py

The names match `lextudio/pysnmp <https://github.com/lextudio/pysnmp>`_, the
other active fork, so code written against either one ports on names alone.

The protocol constants (``usmHMAC192SHA256AuthProtocol`` and friends) are
**not** part of this change and keep their current spelling.

Python 3.10 is the minimum supported version
--------------------------------------------

Support for Python 3.9 and earlier has been dropped, along with the
Python 2-era compatibility fallbacks that surrounded it (``imp``, the
``md5``/``sha`` modules, ``socket.inet_ntop`` shims and the Python 2.6
compatibility directory).

``asyncore`` and ``asynsock`` have been removed
-----------------------------------------------

The ``asyncore`` module was removed from the standard library in Python
3.12. Every carrier and high-level API built on it has been deleted
rather than deprecated:

* ``pysnmp.carrier.asyncore`` and ``pysnmp.carrier.asynsock``
* ``pysnmp.hlapi.asyncore``
* the 61 ``asyncore`` example scripts and their documentation

Applications must use the ``asyncio`` carriers and
``pysnmp.hlapi.asyncio`` instead. The synchronous ``pysnmp.hlapi``
one-liner interface remains available and now runs on ``asyncio``
internally.

``pyasn1.compat.octets`` is no longer used
-------------------------------------------

All uses of the ``pyasn1.compat.octets`` shim were replaced with native
Python 3 equivalents across the codebase. Code that imported
``str2octs``, ``octs2str`` or their siblings from PySNMP modules should
encode and decode with Latin-1 directly.

``pycryptodomex`` imports are now resolved lazily
--------------------------------------------------

``pycryptodomex`` remains a declared runtime dependency, but
``Cryptodome.Cipher`` imports are resolved lazily. PySNMP imports and
serves SNMPv1, SNMPv2c and the SNMPv3 noAuthNoPriv and authNoPriv
security levels without ``pycryptodomex`` installed. Configuring a
privacy protocol without it now raises ``PySnmpError`` naming the
missing package at configuration time, rather than failing later during
packet processing.

Deployments that strip the dependency can still run everything short of
SNMPv3 privacy.

Weak-crypto warnings are emitted at configuration time
-------------------------------------------------------

``addV3User`` now emits ``PySnmpWeakCryptoWarning`` for DES, 3DES and
HMAC-MD5, and ``PySnmpNonStandardCryptoWarning`` for the
Reeder/Blumenthal AES-192/256 variants. Applications that run with
warnings configured as errors will need to filter these explicitly. See
:doc:`/docs/security-considerations` for the recommended configuration.

``pysmi`` API calls use snake_case
------------------------------------

PySNMP now calls the snake_case ``pysmi`` API and the ``pysmi``
dependency pin was widened to allow 2.x. Applications that pass custom
``pysmi`` objects into the MIB compiler must target the same API.

Corrected behaviour that may change results
--------------------------------------------

These are bug fixes, but they change observable behaviour for callers
that depended on the broken semantics:

* ``CommunityData.clone()`` and ``UsmUserData.clone()`` no longer discard
  falsy non-``None`` arguments such as ``mpModel=0``, ``contextName=''``,
  ``authKey=b''`` and ``authKeyType=0``.
* ``ObjectIdentity.__ge__`` and ``__le__`` no longer delegate to ``>``
  and ``<``.
* VACM candidate selection was corrected for matching and ``any``
  security models, permitted security levels, exact contexts and longest
  prefixes.
* SNMP value conversion always clones proxied values into the
  destination ASN.1 type.
* ``ObjectIdentity.__nonzero__`` was removed.
