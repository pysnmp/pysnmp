#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
from pysnmp import debug
from pysnmp.proto import errind, error


# rfc3415 3.2
# noinspection PyUnusedLocal
class Vacm:
    """Void Access Control Model"""

    accessModelID = 0

    def isAccessAllowed(
        self,
        snmpEngine,
        securityModel,
        securityName,
        securityLevel,
        viewType,
        contextName,
        variableName,
    ):
        debug.logger & debug.flagACL and debug.logger(
            f'isAccessAllowed: viewType {viewType} for variableName {variableName} - OK'
        )

        # rfc3415 3.2.5c
        return error.StatusInformation(errorIndication=errind.accessAllowed)
