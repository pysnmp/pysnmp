#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
import socket

from pysnmp import debug

SYMBOLS = {
    "IP_PKTINFO": 8,
    "IP_TRANSPARENT": 19,
    "SOL_IPV6": 41,
    "IPV6_RECVPKTINFO": 49,
    "IPV6_PKTINFO": 50,
    "IPV6_TRANSPARENT": 75,
}

for symbol, value in SYMBOLS.items():
    if not hasattr(socket, symbol):
        setattr(socket, symbol, value)

        debug.logger & debug.flagIO and debug.logger(
            f"WARNING: the socket module on this platform misses option {symbol}. "
            f"Assuming its value is {value}."
        )
