MIB instance generation tools
=============================

The source distribution contains two standalone tools for creating Python
MIB instance modules. Run these commands from a PySNMP source checkout.

IANA Private Enterprise Numbers
-------------------------------

``tools/iana_pen_to_mib.py`` converts the IANA Private Enterprise Numbers
registry into loadable ``MibScalarInstance`` objects. Each symbol is
named ``pen_<number>`` and has the OID ``1.3.6.1.4.1.<number>``. Its
``DisplayString`` value is the registered organization name.

Download the current registry and generate the module:

.. code-block:: console

   $ mkdir -p build
   $ python tools/iana_pen_to_mib.py --output build/IANA-PEN-MIB.py

For reproducible or offline builds, use a previously downloaded registry:

.. code-block:: console

   $ python tools/iana_pen_to_mib.py \
       --input enterprise-numbers.txt \
       --output build/IANA-PEN-MIB.py

Load the generated module and look up an organization:

.. code-block:: console

   $ python examples/smi/manager/load-iana-pen-mib.py \
       build/IANA-PEN-MIB.py 20408
   1.3.6.1.4.1.20408 = PySNMP Project

See :ref:`generated-mib-examples` for the complete Python example.

Instances from an ASN.1 MIB
---------------------------

``tools/mib_instance_generator.py`` compiles an ASN.1 MIB through PySMI and
creates a companion Python module containing placeholder instances for its
scalars and table columns:

.. code-block:: console

   $ python tools/mib_instance_generator.py \
       --mib mibs/EXAMPLE-DEVICE-MIB.txt \
       --asn1-source file:///usr/share/snmp/mibs \
       --output build/EXAMPLE-DEVICE-MIB_instances.py

The compiled definition module (``EXAMPLE-DEVICE-MIB.py``) is written beside
the requested instances module. Keep both files together when configuring a
:class:`~pysnmp.smi.builder.MibBuilder` source.

Use ``--asn1-source`` more than once when imported ASN.1 MIBs live in several
directories or repositories. Use ``--mib-source`` for directories containing
already compiled Python MIB modules. If all dependencies are beside the input
MIB, neither option is necessary.

Scalars receive the conventional ``.0`` suffix. Table-column instances use a
sample index derived from the row's INDEX declaration. Placeholder values are
validated against each object's syntax where possible; edit the generated
module to supply real agent data.

The generated files are regular PySNMP MIB modules:

.. code-block:: console

   $ python examples/smi/agent/load-generated-mib-instances.py \
       EXAMPLE-DEVICE-MIB build/EXAMPLE-DEVICE-MIB_instances.py

See :ref:`generated-mib-examples` for the complete loading example.
