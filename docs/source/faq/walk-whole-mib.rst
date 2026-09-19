
Walking whole MIB
-----------------

Q. The next_cmd() and bulk_cmd() methods of CommandGenerator app 
   (oneliner version) stop working once returned OIDs went out of scope of 
   request OIDs. 
   
   In other words, if I request 1.3.6.1, I would get everything under 
   the 1.3.6.1 prefix, but not 1.3.6.2.  Is there any way to make it walking 
   the whole MIB?

A. Yes, just pass the lexicographicMode=True parameter to CommandGenerator 
   next_cmd() and bulk_cmd() methods (introduced in PySNMP 4.2.3+) or set 
   CommandGenerator.lexicographicMode=True option before calling next_cmd() 
   and bulk_cmd() methods.

.. code-block:: python

    cmdGen = cmdgen.CommandGenerator()
    errorIndication, errorStatus, errorIndex, varBindTable = cmdGen.bulk_cmd(
        ....,
        ....,
        ....,
        lexicographicMode=True
    )
