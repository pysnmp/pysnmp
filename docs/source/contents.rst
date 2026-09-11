
SNMP library for Python
=======================

.. toctree::
   :maxdepth: 2

PySNMP is a cross-platform, pure-`Python <http://www.python.org/>`_
`SNMP <http://en.wikipedia.org/wiki/Simple_Network_Management_Protocol>`_
engine implementation. It features fully-functional SNMP engine capable 
to act in Agent/Manager/Proxy roles, talking SNMP v1/v2c/v3 protocol 
versions over IPv4/IPv6 and other network transports.

Despite its name, SNMP is not really a simple protocol. For instance its
third version introduces complex and open-ended security framework, 
multilingual capabilities, remote configuration and other features. 
PySNMP implementation closely follows intricate system details and features 
bringing most possible power and flexibility to its users.

.. note::

   ``snmpclitools``, which older documentation described as shipping with
   PySNMP, is a separate project and is **not** part of this one. The release
   on PyPI depends on the ``pysnmp`` distribution, which is a different fork
   from a different repository -- installing it beside ``pysnmplib`` puts two
   SNMP engines in one environment.

PySNMP is free and open-source software, distributed under a 2-clause
BSD-style license. The source is at `pysnmp/pysnmp
<https://github.com/pysnmp/pysnmp>`_.

Three other projects are maintained alongside it, and the
`organization site <https://pysnmp.github.io/>`_ describes how they fit
together:

* the `MIB distribution <https://pysnmp.github.io/mibs/>`_, which supplies the
  module definitions an engine resolves names against;
* `pysmi <https://pysnmp.github.io/pysmi/>`_, the MIB compiler, installed with
  the ``compile`` extra;
* `pyasn1 <https://pysnmp.github.io/pyasn1/>`_, the ASN.1 codec underneath
  both, installed with PySNMP itself.

PySNMP library development has been initially sponsored 
by a `PSF <http://www.python.org/psf/>`_ grant.

Quick start
-----------

You already know something about SNMP and have no courage to dive into
this implementation? Try out quick start page!

.. toctree::
   :maxdepth: 2

   /quick-start

Documentation
-------------

.. toctree::
   :maxdepth: 2

   /docs/tutorial
   /docs/api-reference
   /docs/api-internals
   /docs/breaking-changes
   /docs/security-considerations
   /docs/smi-table-api
   /docs/device-report
   /docs/mib-tools
   /docs/mib-corpus
   /docs/loader-contract

Examples
--------

.. toctree::
   :maxdepth: 2

   /examples/contents

Download
--------

Best way is usually to

.. code-block:: bash

   $ pip install pysnmplib

If that does not work for you for some reason, you might need to read the 
following page.

.. toctree::
   :maxdepth: 2

   /download

License
-------

.. toctree::
   :maxdepth: 2

   /license

FAQ
---

.. toctree::
   :maxdepth: 2

   /faq

Further development
-------------------

The changelog is generated from the commit history at release time. The
narrative history of the project through 5.x is kept separately.

.. toctree::
   :maxdepth: 1

   /changelog
   /changelog-history

How changes reach a released version — the branches, the commit-message
conventions, what CI runs and how a release is cut — is documented here.

.. toctree::
   :maxdepth: 2

   /ci-and-releases

Our development plans and new features we consider for eventual implementation
are collected in the following section.

.. toctree::
   :maxdepth: 2

   /development

Contact
-------

In case of questions or troubles using PySNMP, please open up an
`issue <https://github.com/pysnmp/pysnmp/issues>`_ at GitHub or ask at
`Stack Overflow <http://stackoverflow.com/questions/tagged/pysnmp>`_ .
