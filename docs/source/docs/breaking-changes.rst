
.. _breaking-changes:

Breaking Changes
================

This release is not backwards compatible with the 5.0 series. The changes
below require source modifications in applications that used the removed
interfaces. See :doc:`/changelog` for the complete list of changes.

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
