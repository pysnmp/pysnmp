Download PySNMP
===============

.. toctree::
   :maxdepth: 2

The PySNMP software is provided under terms and conditions of BSD-style 
license, and can be freely downloaded from 
`PyPI <https://pypi.org/project/pysnmplib/>`_ or
GitHub (`master branch <https://github.com/etingof/pysnmp/archive/master.zip>`_).


Besides official releases, it's advisable to try the cutting-edge
development code that could be taken from PySNMP
`source code repository <https://github.com/etingof/pysnmp>`_.
It may be less stable in regards to general operation and changes to
public interfaces, but it's first to contain fixes to recently discovered bugs.

The best way to obtain PySNMP and dependencies is to run:

.. code-block:: bash

   $ pip install pysnmplib

In case you are installing PySNMP on an off-line system, the following 
packages need to be downloaded and installed for PySNMP to become 
operational:

* `PyASN1 <https://pypi.python.org/pypi/pyasn1>`_,
  used for handling ASN.1 objects
* `PySNMP <https://pypi.python.org/pypi/pysnmp/>`_,
  SNMP engine implementation

Optional, but recommended:

* `PyCryptodomex <https://pypi.python.org/pypi/pycryptodomex/>`_,
  used by SNMPv3 crypto features
* `PySMI <https://pypi.python.org/pypi/pysmi/>`_ for automatic
  MIB download and compilation. That helps visualizing more SNMP objects
* `Ply <https://pypi.python.org/pypi/ply/>`_, parser generator
  required by PySMI

Install previously downloaded packages with pip, for example:

.. code-block:: bash

   $ python -m pip install --no-index --find-links /path/to/packages pysnmp

In case of any issues, please open a `GitHub issue <https://github.com/etingof/pysnmp/issues/new>`_ so we could try to help out.

