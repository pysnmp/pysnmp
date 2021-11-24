#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
from pysnmp.proto import errind, error
from pysnmp import debug


# rfc3415 3.2
# noinspection PyUnusedLocal
class Vacm:
    """Void Access Control Model"""
    accessModelID = 0

    def isAccessAllowed(self,
                        snmpEngine,
                        securityModel,
                        securityName,
                        securityLevel,
                        viewType,
                        contextName,
                        variableName):
        debug.logger & debug.flagACL and debug.logger(
            f'isAccessAllowed: viewType {viewType} for variableName {variableName} - OK'
        )

        # rfc3415 3.2.5c
        return error.StatusInformation(errorIndication=errind.accessAllowed)
