Download PySNMP
===============

.. toctree::
   :maxdepth: 2

The PySNMP software is provided under terms and conditions of BSD-style 
license, and can be freely downloaded from 
`PyPI <https://pypi.org/project/pysnmplib/>`_ or
GitHub (`main branch <https://github.com/pysnmp/pysnmp/archive/refs/heads/main.zip>`_,
which carries the released line; ``next`` is where work integrates).


Besides official releases, it's advisable to try the cutting-edge
development code that could be taken from PySNMP
`source code repository <https://github.com/pysnmp/pysnmp>`_.
It may be less stable in regards to general operation and changes to
public interfaces, but it's first to contain fixes to recently discovered bugs.

The best way to obtain PySNMP and dependencies is to run:

.. code-block:: bash

   $ pip install pysnmplib

In case you are installing PySNMP on an off-line system, the following 
packages need to be downloaded and installed for PySNMP to become 
operational:

* `pysnmp-pyasn1 <https://pypi.org/project/pysnmp-pyasn1/>`_,
  used for handling ASN.1 objects. This is the fork maintained here; the
  ``pyasn1`` distribution on PyPI is a different project
* `pysnmplib <https://pypi.org/project/pysnmplib/>`_,
  SNMP engine implementation
* `PyCryptodomex <https://pypi.python.org/pypi/pycryptodomex/>`_,
  used by SNMPv3 crypto features. It is a declared dependency, but its
  ciphers are imported lazily: SNMPv1, SNMPv2c and the SNMPv3
  noAuthNoPriv and authNoPriv security levels work without it installed.

Optional, and installed by asking for the ``compile`` extra:

.. code-block:: bash

   $ pip install 'pysnmplib[compile]'

* `pysnmp-pysmi <https://pypi.org/project/pysnmp-pysmi/>`_ for automatic
  MIB download and compilation. That helps visualizing more SNMP objects.
  As with pyasn1, this is the fork maintained here rather than the ``pysmi``
  distribution
* `Ply <https://pypi.org/project/ply/>`_, parser generator
  required by pysmi

PySMI is not a required dependency. PySNMP ships a rendering of the standard
modules an engine resolves while starting up and while being configured, so
SNMPv1, SNMPv2c, SNMPv3 and name resolution all work without it. What the extra
buys is compiling ASN.1 MIB sources at run time; ask for a MIB compiler without
it and :py:class:`~pysnmp.smi.error.SmiError` is raised, naming the missing
import.

Install previously downloaded packages with pip, for example:

.. code-block:: bash

   $ python -m pip install --no-index --find-links /path/to/packages pysnmplib

Neither the extra nor an off-line install gives you MIB *content*. Module
definitions come from the `MIB distribution <https://pysnmp.github.io/mibs/>`_,
which is used live over HTTPS or installed locally from a release archive or an
OCI image -- none of which is a pip install. PySNMP starts without it, on the
standard modules it ships.

In case of any issues, please open a `GitHub issue <https://github.com/pysnmp/pysnmp/issues/new>`_ so we could try to help out.

