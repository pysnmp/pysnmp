Diffie-Hellman USM key change
=============================

:RFC:`2786` defines ``SNMP-USM-DH-OBJECTS-MIB``, which changes a USM key by
agreeing a new one over the wire. Neither the old key nor the new one is ever
transmitted, and -- unlike the :RFC:`3414` ``usmUserAuthKeyChange`` this engine
has always supported -- the old key is not needed to perform the change. Only
write access to the row is. That is what makes provisioning an agent remotely
practical rather than a chicken-and-egg problem.

How the exchange works
----------------------

The agent publishes Diffie-Hellman parameters in ``usmDHParameters`` and, for
each row of ``usmDHUserKeyTable``, a public value. A manager reads both, offers
a public value of its own, and both sides arrive at a shared secret neither
sent. The new key is the right-most bits of that secret -- as many as the row's
authentication or privacy protocol needs.

The key that results is already localized to the agent: it is derived from a
secret only that agent could have computed, so it is used directly rather than
being run through :RFC:`3414` key localization.

Changing a key
--------------

:func:`~pysnmp.hlapi.asyncio.dh_key_change` runs the whole exchange:

.. literalinclude:: /../../examples/hlapi/asyncio/manager/cmdgen/usm-dh-key-change.py
   :language: python

:download:`Download the asyncio example
</../../examples/hlapi/asyncio/manager/cmdgen/usm-dh-key-change.py>`.

The synchronous facade offers the same call under
``pysnmp.hlapi.dh_key_change``, blocking until the exchange completes.

Using the result
----------------

The agent installs the new key when the SET commits, so the credentials that
ran the change stop working the moment it returns. Build fresh credentials from
the result, which carries both halves of what
:py:class:`~pysnmp.hlapi.UsmUserData` needs:

* ``key`` -- the new localized key, passed with
  ``authKeyType=usmKeyTypeLocalized`` (or ``privKeyType`` for a privacy key).
* ``securityEngineId`` -- the agent's authoritative engine ID. A localized key
  is bound to one engine and USM will not accept it without being told which,
  so this is not optional. The exchange learns it from the row index, which
  saves a separate discovery.

Anything that fails raises :class:`~pysnmp.hlapi.asyncio.DHKeyChangeError` rather than
returning an error indication, because a key change that half happened leaves
the caller unable to reach the agent.

When the SET is the step that fails
-----------------------------------

Everything the result needs is derived before the SET, so a parameter or key
length that cannot produce a key is refused while the agent is still untouched.

The SET itself is the step that cannot be taken back, and its failure is
ambiguous. SNMP over UDP gives no way to tell a refused SET from one that
committed and whose response was lost, and :RFC:`2786` defines no recovery for
that. A transport target with retries makes it likelier to surface as
``wrongValue`` than as a timeout, because a successful SET makes the agent
publish a fresh public value, so the retransmitted copy no longer matches the
half it echoes.

So the exception carries what is needed to find out:

.. code-block:: python

   try:
       result = dh_key_change(engine, current, target, ContextData())
   except DHKeyChangeError as exc:
       if exc.candidate is not None:
           # The agent may have re-keyed to this. Try it before concluding
           # that the old credentials are still live.
           ...
       raise

Pass a transport target with ``retries=0`` if a timeout is the clearer signal
for your recovery path; the exchange does not override the retry policy it is
given.

Finding the row
---------------

``usmDHUserKeyTable`` is indexed by engine ID and user name. By default the
table is walked to find the row for the user being changed, so callers do not
need to know the engine ID in advance. An agent that does not permit walking
the table can be addressed directly by passing ``securityEngineId``.

What is supported
-----------------

The manager side of the key change is implemented: all four ``DHKeyChange``
columns, for authentication and privacy keys, for a named user or for the
agent's own key. ``pysnmp.proto.secmod.rfc2786`` also provides the kickstart
key derivation (PBKDF2 with the salts the MIB fixes) for reading a
``usmDHKickstartTable``.

The agent side is not implemented -- pysnmp does not serve these objects -- and
no agent-side implementation of ``usmDHKickstartTable`` is known to exist to
interoperate with.

None of this needs a cryptographic library: the agreement is modular
exponentiation, and the one derivation the RFC names is PBKDF2 from
:mod:`hashlib`.

Interoperability
----------------

The exchange is tested end to end against Net-SNMP in CI, under the ``v3-dh``
profile of the Net-SNMP integration workflow. That profile runs an agent built
with the ``snmp-usm-dh-objects-mib`` module, which is not in Net-SNMP's default
module set and which distribution packages -- Debian's ``snmpd`` among them --
leave out. An agent without it answers ``noSuchObject`` for the whole
``1.3.6.1.3.101`` subtree.

The test asserts more than that the exchange completed: it authenticates with
the derived key afterwards, which is the only way to observe that the key the
agent installed is the key this engine computed.


API reference
-------------

.. autofunction:: pysnmp.hlapi.asyncio.dh_key_change

.. autoclass:: pysnmp.hlapi.asyncio.DHKeyChangeResult

.. autoclass:: pysnmp.proto.secmod.rfc2786.DHParameters
   :members:

.. autoclass:: pysnmp.hlapi.asyncio.DHKeyChangeError
   :members:
