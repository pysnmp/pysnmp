
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
``usmAesCfb128Protocol``                   Recommended    RFC 3826; the only standards-track
                                                          privacy protocol for SNMPv3
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
