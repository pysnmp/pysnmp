#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The absence of authentication, as a service the model can call."""

from pysnmp.proto import errind, error
from pysnmp.proto.secmod.rfc3414.auth import base


class NoAuth(base.AbstractAuthenticationService):
    """No authentication: computes no digest and accepts any message."""

    serviceID: tuple[int, ...] = (1, 3, 6, 1, 6, 3, 10, 1, 1, 1)  # usmNoAuthProtocol

    def hashPassphrase(self, authKey):
        """Nothing to hash: there is no key at this security level."""
        return

    def localizeKey(self, authKey, snmpEngineID):
        """Nothing to localize: there is no key at this security level."""
        return

    # 7.2.4.2
    def authenticateOutgoingMsg(self, authKey, wholeMsg):
        """Always fails -- asking to authenticate with no authentication is a mistake.

        Reached only where the security level and the protocol disagree, so it reports
        rather than sending something the peer will reject.
        """
        raise error.StatusInformation(errorIndication=errind.noAuthentication)

    def authenticateIncomingMsg(self, authKey, authParameters, wholeMsg):
        """Always fails, for the same reason as the outgoing side."""
        raise error.StatusInformation(errorIndication=errind.noAuthentication)
