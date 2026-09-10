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


Several corpora at once
-----------------------

A deployment rarely has one corpus. It has the distribution's, covering the
standard modules and whatever vendors shipped with it, and it has its own --
the enterprise MIBs its devices actually speak, which nobody else publishes.
``CompositeMibCorpus`` searches several as one:

.. code-block:: python

   from pysnmp.smi.corpus import open_corpora

   mibBuilder.setMibCorpus(open_corpora(["/mibs/site.db", "/mibs/core.db"]))

Or from the environment, which is the same thing without the imports:

.. code-block:: shell

   PYSNMP_MIB_DBS=/mibs/site.db:/mibs/core.db

Like ``PYSNMP_MIB_DIRS``, it is an ``os.pathsep``-separated list read when a
``MibBuilder`` is constructed, and the order is the precedence order. A path
naming something that is not a readable corpus raises ``SmiError`` there and
then, rather than being skipped: a skipped corpus leaves a deployment resolving
fewer modules than it asked for, and the only symptom is a MIB that used to be
found and now is not.

**The newest MODULE-IDENTITY revision wins; configured order only breaks the
tie.** This is the rule ``MibBuilder`` already applies to two MIB sources
carrying one module, and the rule pysmi's compiler applies to two copies of one
MIB, applied here to corpora. Two corpora carrying a module are carrying the
same specification at two revisions, and the newer one is the answer wherever
it sits in the search path -- so configuring a corpus that happens to carry an
older copy cannot silently roll that module back.

Order settles what revisions cannot: when a candidate states no revision at all
-- every SMIv1 module, and the SMI modules themselves -- or when they all state
the same one.

**By OID, the longest prefix wins first.** Given a site subtree under an arc the
core corpus already anchors, first-match-wins would resolve every OID beneath it
to the core corpus's shallow anchor and never reach the site corpus at all -- no
matter which was configured first:

.. code-block:: python

   store = open_corpora(["/mibs/core.db", "/mibs/site.db"])

   # core.db anchors 1.3.6.1.4.1.9; site.db anchors the subtree itself.
   store.find_module("1.3.6.1.4.1.9.9.42.1.1")   # -> 'SITE-MIB'

The revision rule settles only what a shorter prefix cannot: two corpora naming
*different* modules at the same prefix length.

**Both paths reach the same copy.** An OID resolves to a module name, and that
name then goes through the revision rule like any other. A corpus can anchor an
OID without owning the module it names -- the anchor says which module answers,
and the revision says whose copy of it is read.

**One module resolves from exactly one corpus.** Where two carry the same
module, every name-keyed lookup for it routes to the same one and the other's
rows for it are invisible -- not its nodes, not its types, not its IMPORTS.
Merging them would build one module from two definitions and produce two
classes for one type, which fails ``isinstance`` somewhere far from here.

``loadTexts`` is reported for the composite only when *every* corpus carries
prose, so one textless corpus in the search path makes the whole composite
textless rather than silently answering with no DESCRIPTION for the modules it
owns. What that then means is the subject of `What a corpus does not carry`_.


Which copy answered
-------------------

A module can be carried by a directory, a package, the wheel, a corpus and the
compiler's output all at once, and exactly one of them answers. Which one is not
readable from the path: a wheel and a directory of overrides are both
directories under ``site-packages``, and a corpus is not a path in that sense at
all.

.. code-block:: python

   builder.loadModule("IF-MIB")

   builder.getModuleProvenance("IF-MIB")
   # -> (MibSourceKind.DB, '/mibs/vendor.db')

   builder.getModulePath("IF-MIB")
   # -> 'corpus:/mibs/vendor.db/IF-MIB'

The kind is one of ``override`` (pysnmp's own copies of the engine MIBs),
``wheel``, ``dir``, ``pkg``, ``db`` or ``compiled``; the id names the particular
source, which is what tells a distro corpus from a customer one. A module that
is not loaded has no provenance, and unloading it forgets what it had --
reloading can well pick a different copy.

It is tracked per module rather than per node, because a module resolves from
exactly one source: a per-node record would be the same answer repeated across
every OID in the module.


What was passed over
--------------------

The other half of the same question. A leftover ``.py`` directory that a corpus
was meant to replace still outranks the corpus, so the corpus is the copy being
skipped -- the opposite of what adding one usually means.

.. code-block:: python

   builder.shadowedModules()
   # -> {'IF-MIB': [(MibSourceKind.DIR, '/opt/mibs'),
   #                (MibSourceKind.DB, '/mibs/core.db')]}

   builder.reportShadowedModules()   # same answer, and says so out loud

``reportShadowedModules()`` runs by itself inside ``loadModules()`` when it is
called with no names, since that path already enumerates every source and the
enumeration is the whole cost. Loading modules by name does not trigger it; call
it directly there.

How loudly is ``moduleConflictSeverity``:

``warn`` (default)
    One ``PySnmpShadowedModuleWarning`` per shadowed module.

``error``
    Raises ``SmiError`` before anything is loaded. The setting for a deployment
    that has finished migrating off generated ``.py`` and wants any survivor to
    be fatal.

``silent``
    Says nothing, still returns the answer.

Two things it deliberately does not do. It **never claims the copies differ, or
match**: answering that means reading and normalizing both, which is the work a
corpus exists to avoid, so it reports only that a second copy exists and is
being passed over. And it **says nothing about a stock install**, where
``pysnmp.smi.mibs`` shadows the wheel for the seven modules the engine needs --
that is what the search order is for, and warning about it would mean warning
every user who configured nothing. ``shadowedModules()`` still reports it, being
a question about the sources rather than about the configuration.


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
``loadTexts = False``, and the one consumer that wants them -- a MIB browser --
has two other ways to get them: pysmi's published ``json/`` tree, and the
compiler.

So a corpus cannot satisfy ``loadTexts``. What happens when it is asked to
depends on whether anything else can.

Corpus for speed, compiler for prose
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure both. The corpus resolves the thousands of modules a deployment
touches, cheaply and without executing anything; the compiler renders the few
whose text is going on screen:

.. code-block:: python

   mibBuilder.setMibCorpus(MibCorpus("/mibs/core.db"))
   mibBuilder.setMibCompiler(mibCompiler, destDir)
   mibBuilder.loadTexts = True

   mibBuilder.loadModules("IF-MIB")   # compiled from ASN.1, DESCRIPTION intact

Sources are searched first, then the corpus, and only for a module neither
carried does the compiler run. Under ``loadTexts`` the corpus **steps aside**
rather than answering with no prose, so the module falls through to the
compiler and comes back with its text. Clear ``loadTexts`` and the corpus
answers again, without compiling anything.

Two consequences worth knowing:

* Only ``loadModules()`` compiles. ``loadModule()`` never has, so a corpus that
  steps aside there raises ``MibNotFoundError`` -- which is what it already
  raises for a module nothing carries.
* ``setMibCompiler()`` puts its output directory on the search path, so a
  module compiled once is the copy every later load finds. The corpus does not
  take it back when ``loadTexts`` is cleared again.

With no compiler configured
~~~~~~~~~~~~~~~~~~~~~~~~~~~

There is nothing to fall through to, so the request is refused:

.. code-block:: python

   mibBuilder.setMibCorpus(corpus)
   mibBuilder.loadTexts = True
   mibBuilder.loadModules("IF-MIB")   # raises SmiError

Refused rather than silently satisfied: a caller that asked for descriptions
and got a module with none has no way to tell that from a MIB that declares
none. Attach a compiler, read the text from the ``json/`` tree, or clear
``loadTexts``.

Attaching the corpus is not where this is decided. A compiler may be attached
after a corpus is, so refusing at ``setMibCorpus()`` would make a working
configuration depend on the order the two were set up in.


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
