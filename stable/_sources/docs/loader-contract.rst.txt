MIB module loader contract
==========================

A generated MIB module is Python that calls into ``MibBuilder`` and the SMI
classes. This page states what those calls may assume.

It exists because the assumptions were previously undocumented, so a code
generator had to infer them. Generated output carries the evidence:

.. code-block:: python

   if getattr(mibBuilder, 'version', (0, 0, 0)) > (4, 4, 0):
       ifStackGroup = ifStackGroup.setStatus('deprecated')

The ``getattr`` default exists because the generator could not assume the
attribute is present. The version comparison exists because it could not assume
the setter is available. Neither assumption was ever wrong; both were unstated,
so the generator hedged.

Inference also goes stale silently. pysmi carries a list of classes it believes
do not implement ``setReference()``, and suppresses REFERENCE text for them. All
three implement it, so REFERENCE clauses are dropped from generated modules for
no reason (pysnmp/pysmi#194).

.. contents::
   :local:
   :depth: 1


Versioning
----------

.. code-block:: python

   >>> from pysnmp.smi.builder import MibBuilder
   >>> MibBuilder.loaderContract
   (1, 0)

A generator targets a contract version rather than a pysnmp version. The two
move at different rates: ``version`` changes every release, ``loaderContract``
only when this page changes.

The minor part increases when something is **added** -- a new class, a new
setter, a new accepted argument form. A generator written against ``(1, 0)``
keeps working against ``(1, 5)``.

The major part increases when something is **removed or changed**: a setter
withdrawn, an argument shape altered, a return contract broken. That is a
breaking change and is released as one.

``tests/test_loader_contract.py`` asserts everything on this page. A change that
breaks it is a contract change, not an implementation detail.


Contract v1
-----------

Builder attributes
~~~~~~~~~~~~~~~~~~

===================  ==============================================================
Attribute            Guarantee
===================  ==============================================================
``version``          Always present, always a tuple of integers. ``getattr`` with
                     a default is unnecessary.
``loaderContract``   Always present, ``(major, minor)`` tuple.
``moduleID``         The string ``"PYSNMP_MODULE_ID"``.
``loadTexts``        Boolean, ``False`` on a fresh builder.
===================  ==============================================================

``loadTexts`` is the flag a generated module guards its text setters with:

.. code-block:: python

   if mibBuilder.loadTexts:
       ifIndex.setDescription('A unique value, greater than zero...')

When it is false the setter is skipped, so a text setter must never carry
information the module needs in order to resolve.

Symbol exchange
~~~~~~~~~~~~~~~

``importSymbols(modName, *symNames)`` returns a tuple of objects in the order
requested, loading ``modName`` if it is not loaded. It raises
``MibNotFoundError`` when the module cannot be found, and ``SmiError`` when the
module loads but does not define a requested symbol, or when ``modName`` is
empty.

``exportSymbols(modName, **namedSyms)`` publishes what the module defines.
Three behaviours a generator relies on:

* exporting a name twice under one module raises ``SmiError``. A generated
  module must therefore export each symbol once
* every exported symbol except ``PYSNMP_MODULE_ID`` is renamed to its label when
  it has one, and given the export key as its label when it does not
* ``PYSNMP_MODULE_ID`` is exempt from that rewriting and keeps the key it was
  exported under

SMI classes and setters
~~~~~~~~~~~~~~~~~~~~~~~

Every setter listed here exists at contract v1 and may be called without a
version guard. Each returns the node, so calls chain.

From ``SNMPv2-SMI``:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Class
     - Setters
   * - ``MibScalar``
     - ``setDescription``, ``setLabel``, ``setMaxAccess``, ``setReference``,
       ``setStatus``, ``setSyntax``, ``setUnits``
   * - ``MibTable``
     - as ``MibScalar``
   * - ``MibTableRow``
     - as ``MibScalar``, plus ``setIndexNames``
   * - ``MibTableColumn``
     - as ``MibScalar``
   * - ``MibIdentifier``
     - ``setLabel``
   * - ``ObjectIdentity``
     - ``setDescription``, ``setLabel``, ``setReference``, ``setStatus``
   * - ``NotificationType``
     - ``setDescription``, ``setLabel``, ``setObjects``, ``setReference``,
       ``setStatus``
   * - ``ModuleIdentity``
     - ``setContactInfo``, ``setDescription``, ``setLabel``, ``setLastUpdated``,
       ``setOrganization``, ``setReference``, ``setRevisions``, ``setStatus``

From ``SNMPv2-CONF``:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Class
     - Setters
   * - ``ObjectGroup``
     - ``setDescription``, ``setLabel``, ``setObjects``, ``setReference``,
       ``setStatus``
   * - ``NotificationGroup``
     - as ``ObjectGroup``
   * - ``ModuleCompliance``
     - as ``ObjectGroup``
   * - ``AgentCapabilities``
     - ``setDescription``, ``setLabel``, ``setProductRelease``,
       ``setReference``, ``setStatus``

**``setReference`` is available on every class that carries it above, including
the four conformance classes.** RFC 2580 permits REFERENCE on those macros, and
pysnmp accepts it. A generator must not suppress REFERENCE for them.

Argument shapes
~~~~~~~~~~~~~~~

``setObjects(*pairs)``
    Each pair is ``(module, symbol)``. ``getObjects()`` returns them in order.

``setIndexNames(*triples)``
    Each triple is ``(implied, module, symbol)`` -- **implied first**, as an
    integer 0 or 1, not a boolean. ``getIndexNames()`` returns them in order.

``setLastUpdated(stamp)`` and ``setRevisions(stamps)``
    ASN.1 UTC time strings, stored verbatim and returned unchanged. pysnmp does
    not parse or normalize them; a caller that needs a date parses the string.

``setStatus(status)``
    The SMI status token as a string. pysnmp does not translate between the
    SMIv1 and SMIv2 vocabularies, so a module's own is preserved.


What is deliberately not in the contract
----------------------------------------

Not stated here, and therefore not something a generator may rely on:

* the class hierarchy above these classes, and any method not listed
* ``MibScalarInstance``, which is for instrumentation rather than generated
  translation modules
* internal state -- ``mibSymbols``, ``lastBuildId``, anything underscored
* the order in which a module's symbols are exported
* anything about how a module is located on disk, which is
  ``MibSource`` behaviour rather than loader behaviour


For generator authors
---------------------

Targeting contract v1 means:

* read ``MibBuilder.loaderContract`` rather than ``version``, and guard on the
  contract only when you support more than one
* emit setter calls from the tables above with no version guard
* emit REFERENCE wherever the MIB declares it, for every class listed
* guard text setters on ``mibBuilder.loadTexts`` and nothing else
* export each symbol exactly once, and export the module identity as
  ``PYSNMP_MODULE_ID``

If something you need is not on this page, it is not in the contract. Ask for it
to be added rather than inferring it from the implementation -- that inference is
what this page replaces.
