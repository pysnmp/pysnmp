
.. _security-considerations:

Security Considerations
=======================

.. toctree::
   :maxdepth: 2

SNMPv3 defines a range of authentication and privacy protocols. Several of
them date from the late 1990s and are no longer considered safe, but remain
implemented in PySNMP because deployed equipment still speaks nothing else.
This page states which combinations to choose and which to avoid.

Recommended configuration
-------------------------

Use AES-128-CFB for privacy and HMAC-SHA-256 for authentication:

.. code-block:: python

    from pysnmp.entity import config

    config.addV3User(
        snmpEngine,
        'my-user',
        authProtocol=config.usmHMAC192SHA256AuthProtocol,
        authKey='my-authentication-key',
        privProtocol=config.usmAesCfb128Protocol,
        privKey='my-privacy-key',
    )

Always use the ``authPriv`` security level. ``authNoPriv`` leaves every varbind
value readable on the wire, and ``noAuthNoPriv`` offers no protection at all.

Protocol status
---------------

Authentication protocols
~~~~~~~~~~~~~~~~~~~~~~~~

=========================================  ===========  ======================================
Protocol                                   Status       Notes
=========================================  ===========  ======================================
``usmHMAC192SHA256AuthProtocol``           Recommended  RFC 7860
``usmHMAC256SHA384AuthProtocol``           Acceptable   RFC 7860
``usmHMAC384SHA512AuthProtocol``           Acceptable   RFC 7860
``usmHMAC128SHA224AuthProtocol``           Acceptable   RFC 7860
``usmHMACSHAAuthProtocol``                 Acceptable   RFC 3414; SHA-1 collisions do not
                                                        affect its use as an HMAC
``usmHMACMD5AuthProtocol``                 Deprecated   MD5 deprecated by RFC 6151
``usmNoAuthProtocol``                      Unsafe       No authentication
=========================================  ===========  ======================================

Privacy protocols
~~~~~~~~~~~~~~~~~

=========================================  =============  ====================================
Protocol                                   Status         Notes
=========================================  =============  ====================================
``usmAesCfb128Protocol``                   Recommended    RFC 3826; recommended standards-track
                                                          privacy option for SNMPv3
``usmAesCfb192Protocol``                   Non-standard   Reeder draft; needed for some
``usmAesCfb256Protocol``                                  vendors, including Cisco
``usmAesBlumenthalCfb192Protocol``         Non-standard   Blumenthal draft, expired
``usmAesBlumenthalCfb256Protocol``
``usm3DESEDEPrivProtocol``                 Unsafe         64-bit block, vulnerable to Sweet32
                                                          (CVE-2016-2183); disallowed for
                                                          encryption by NIST SP 800-131A Rev 2
``usmDESPrivProtocol``                     Broken         56-bit effective key, brute-forcible;
                                                          disallowed by NIST SP 800-131A
``usmNoPrivProtocol``                      Unsafe         No encryption
=========================================  =============  ====================================

The AES-192 and AES-256 variants are cryptographically sound. They are marked
non-standard because their key localisation was never standardised by the
IETF: the Reeder and Blumenthal drafts expired without becoming RFCs, and the
two disagree on how to extend a localised key. Choosing one of them ties your
configuration to equipment implementing the same draft.

Configuration warnings
----------------------

Configuring a weak or non-standard protocol emits a warning at configuration
time, not at packet processing time:

* :class:`pysnmp.error.PySnmpWeakCryptoWarning` — the protocol is no longer
  considered cryptographically safe.
* :class:`pysnmp.error.PySnmpNonStandardCryptoWarning` — the protocol is sound
  but was never standardised.

Both derive from :class:`pysnmp.error.PySnmpCryptoWarning`, which derives from
:class:`UserWarning` rather than :class:`DeprecationWarning` so that the
warnings stay visible under Python's default warning filters.

If you must talk to legacy equipment and have accepted the risk, silence them
selectively:

.. code-block:: python

    import warnings
    from pysnmp.error import PySnmpWeakCryptoWarning

    warnings.filterwarnings('ignore', category=PySnmpWeakCryptoWarning)

Turning SNMPv1 and SNMPv2c off
------------------------------

SNMPv1 and SNMPv2c authenticate with a community string sent in the clear.
There is no cipher to be weak here and nothing to configure better: the
credential is readable by anyone who can see the packet, and a request carrying
the right string is honoured whoever sent it.

Regulated environments generally have to do more than avoid using them. They
have to be able to say the engine *cannot* use them, which is a different
claim, and one that a code review of the calling application does not settle.
Build the engine without them:

.. code-block:: python

    from pysnmp.entity.engine import SnmpEngine

    snmpEngine = SnmpEngine(enableLegacyVersions=False)

Or, for an application that offers no way to pass the argument, set the
environment variable and leave the application alone:

.. code-block:: bash

    export PYSNMP_DISABLE_V1_V2C=1

An explicit ``enableLegacyVersions`` argument always wins over the variable, so
a process that deliberately builds a legacy engine — a proxy translating v2c to
v3, say — still can.

What the guarantee rests on
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The v1 and v2c message processing and security models are not registered on the
engine at all. Enforcement is subtraction rather than a check, which matters
for what you can claim about it:

* **Inbound.** :RFC:`3412#section-4.2.1.2` says a message whose ``msgVersion``
  has no message processing model is counted in ``snmpInBadVersions`` and
  dropped. A v3-only engine rejects a v1 message exactly as it rejects a
  version that does not exist. The message is never dispatched, no community
  is ever compared, and the drop is counted where an audit can read it.
* **Outbound.** ``MsgAndPduDispatcher.sendPdu()`` raises
  ``unsupportedMsgProcessingModel``. Nothing community-authenticated can leave
  the engine.
* **Configuration.** ``pysnmp.entity.config.addV1System()`` raises
  :class:`pysnmp.error.PySnmpError` rather than building a row that could
  never be used, so a mistake surfaces at the line that made it. Anything
  reaching pysnmp through :class:`~pysnmp.hlapi.auth.CommunityData` reaches
  this function, so the high-level API fails the same way.

There is no configuration that re-enables a version on an engine already built
without it. Rebuild the engine.

Configuring a community on an engine that *does* allow it emits
:class:`pysnmp.error.PySnmpWeakCryptoWarning`, the same way a weak cipher does.
The default is unchanged — every engine still speaks all three versions unless
told otherwise — and the warning is silenced the same way as the others.

Cipher backend
--------------

SNMPv3 privacy is the only part of PySNMP that needs a block cipher. It is
provided by `pycryptodomex <https://pycryptodome.readthedocs.io>`_, which is a
required dependency because the recommended AES-128-CFB protocol depends on it.

The cipher backend is imported lazily, on first use. If pycryptodomex has been
stripped from an installation, PySNMP still imports and serves SNMPv1, SNMPv2c
and the SNMPv3 ``noAuthNoPriv`` and ``authNoPriv`` security levels; configuring
a privacy protocol then raises :class:`pysnmp.error.PySnmpError` naming the
missing package.
