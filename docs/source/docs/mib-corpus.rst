.. _mib-corpus:

Loading MIBs from a corpus
==========================

A **MIB corpus** is a SQLite database holding the SMI model as data: one row
per node, keyed for lookup by OID and by name, and ordered so a GETNEXT walk is
a range query. pysmi builds it (``mibcorpus --emit=core-db``) and pysnmp reads
it with the standard library.

It is **opt-in and additive**. Everything on this page is something you have to
ask for. A ``MibBuilder`` with no corpus configured resolves exactly as it
always has, and configuring one does not change what a module already on disk
resolves to.

.. contents::
   :local:
   :depth: 2


Nothing changes unless you ask
------------------------------

This is the compatibility promise, and it is worth stating before the feature:

* A ``MibBuilder`` with no corpus behaves identically to one from before this
  existed -- same sources, same search order, same objects, same errors.
* With a corpus configured, a module the MIB sources carry is still loaded
  from the MIB sources. The corpus is where a module is found when nothing
  else has it.
* The corpus is consulted **before** the MIB compiler, so a deployment with
  ``addMibCompiler()`` set up keeps compiling whatever the corpus does not
  carry.

So an existing deployment upgrades into this by doing nothing, and opts in by
adding two lines.


Why you might want one
----------------------

The published ``index-v2.csv`` already answers *which module owns this OID*, so
lazy loading needs no corpus at all. Two things it cannot do are the reason
this exists.

**It cannot tell you what is at an OID.** The index is ``MODULE,OID`` and
carries a module's *anchors*, so a leaf like ``ifDescr`` is not in it. Getting
from an OID to a name, a syntax and an access level means loading the module --
by compiling its ASN.1 on the trap path, or by parsing its whole JSON document.
On ``CISCO-ENTITY-VENDORTYPE-OID-MIB`` that is 11 ms and 9,773 symbols to reach
one of them; from a corpus it is one indexed row.

**It cannot tell you what comes next.** An anchor index has no per-node
ordering, so a walk cannot be served from one.

There is a third reason, which is about what a corpus *is not*: a pysnmp MIB
module is Python that ``MibBuilder`` runs through ``exec()``. A corpus is rows.
Building a module from rows executes nothing.


Using one
---------

.. code-block:: python

   from pysnmp.smi.builder import MibBuilder
   from pysnmp.smi.corpus import MibCorpus

   mibBuilder = MibBuilder()
   mibBuilder.setMibCorpus(MibCorpus("/mibs/core.db"))

   # Resolves from the MIB sources if they have it, from the corpus if not.
   (ifDescr,) = mibBuilder.importSymbols("IF-MIB", "ifDescr")

With the SNMP engine:

.. code-block:: python

   from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

   snmpEngine = SnmpEngine()
   mibBuilder = snmpEngine.get_mib_builder()
   mibBuilder.setMibCorpus(MibCorpus("/mibs/core.db"))

Pass ``None`` to stop using one. The corpus is opened read-only with SQLite's
``immutable=1``, so it takes no locks and needs nothing writable near it --
which is what lets it be mounted from a Kubernetes image volume.


Resolving a trap OID without a compiler
---------------------------------------

The corpus can be queried directly, which is what a trap receiver wants: an
arriving OID is an *instance* OID -- a column OID plus index arcs -- and
appears in no MIB at all.

.. code-block:: python

   corpus = MibCorpus("/mibs/core.db")

   # Which module answers for it? Longest-prefix, chopping an arc at a time.
   corpus.find_module("1.3.6.1.2.1.2.2.1.2.7")     # -> 'IF-MIB'

   # What is the node itself?
   corpus.node("1.3.6.1.2.1.2.2.1.2")["name"]      # -> 'ifDescr'

   # GETNEXT, over the whole corpus.
   corpus.next_node("1.3.6.1.2.1.2.2.1.2")["name"] # -> 'ifType'

   # Everything under a subtree, in OID order.
   corpus.subtree("1.3.6.1.2.1.2.2")

``find_module`` returning ``None`` is a **miss, not an error**: an OID nothing
claims still decodes structurally as far as the longest known prefix reaches,
and that is the behaviour a trap receiver wants.

This replaces the older pattern of parsing ``index.csv`` into a dictionary and
calling ``loadModules()`` on whatever it named. That pattern works and is not
going away yet, but it needs a second file, a full ASN.1 compile per module on
the trap path, and it cannot answer either of the questions above.


What a corpus does not carry
----------------------------

**Prose.** No DESCRIPTION, no REFERENCE. They are roughly a third of a
generated module's bytes, the runtime discards them under the default
``loadTexts = False``, and pysmi's published ``json/`` tree already serves the
one consumer that wants them -- a MIB browser.

Because of that, ``setMibCorpus()`` **refuses** a textless corpus when
``loadTexts`` is set:

.. code-block:: python

   mibBuilder.loadTexts = True
   mibBuilder.setMibCorpus(corpus)   # raises SmiError

Refused rather than silently satisfied: a caller that asked for descriptions
and got a module with none has no way to tell that from a MIB that declares
none. Load texts from the ``json/`` tree, or clear ``loadTexts``.


How a module is built
---------------------

The objects are the ones the generated module would have produced --
``MibScalar``, ``MibTable``, ``MibTableRow``, ``MibTableColumn``,
``NotificationType`` and the rest -- with the same OIDs, the same syntax
instances, the same ``maxAccess`` and the same index names. What differs is
that the description of them arrived as data.

Type names resolve in this order:

1. A type the module declares itself. Its own TEXTUAL-CONVENTION shadows
   anything of that name elsewhere.
2. A base SMI type -- ``Integer32``, ``OCTET STRING``, ``Counter64`` and so on.
3. Whatever the module's IMPORTS clause says defines it. This may load that
   module, from disk or from the corpus, so a vendor module's ``DisplayString``
   resolves to the one the already-loaded ``SNMPv2-TC`` exported.

A type that resolves nowhere raises rather than falling back to a base type: a
column silently typed ``OctetString`` instead of its TEXTUAL-CONVENTION renders
every value wrong and looks like a device fault.

A syntax is stored once in the corpus and referenced by id, and the class built
for it is cached against that id, so two objects sharing a type share a class
and ``isinstance`` never sees two classes for one type.


Version gating
--------------

A corpus stamps a **schema version** -- the layout, which changes rarely -- and
a **corpus version**, which is the build and changes often. They are separate
so that a corpus rebuild does not require a pysnmp release.

``MibCorpus`` refuses a schema version it does not implement, rather than
reading the part it recognizes: a partial read resolves some OIDs and silently
not others.

.. code-block:: python

   corpus.meta("schema_version")   # '1'
   corpus.meta("corpus_version")   # whatever the build stamped
   corpus.module("IF-MIB")         # tier, revision, content hash, node count

The full file format is specified in pysmi's ``corpus-schema`` document, and
pysmi publishes a conformance fixture that this repository's CI runs against
this reader -- so the two halves of the contract are checked against each other
rather than against themselves.
