#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Lazy access to the pycryptodomex block cipher backend.

SNMPv3 privacy (encryption) is the only part of pysnmp that needs a block
cipher. Resolving the backend on first use rather than at import time keeps
SNMPv1, SNMPv2c and the SNMPv3 noAuthNoPriv/authNoPriv security levels usable
in environments where pycryptodomex has been stripped from the install.
"""

from functools import lru_cache

INSTALL_HINT = (
    "SNMPv3 privacy requires the 'pycryptodomex' package, which could not be "
    "imported. Install it with 'pip install pycryptodomex'."
)


@lru_cache(maxsize=None)
def getCipher(name: str):
    """Return the named ``Cryptodome.Cipher`` module, or None if unavailable.

    Parameters
    ----------
    name : str
        Cipher module name, e.g. ``AES``, ``DES`` or ``DES3``.

    Returns
    -------
    module or None
        The cipher module, or None when pycryptodomex is not installed.
    """
    try:
        from importlib import import_module

        return import_module(f'Cryptodome.Cipher.{name}')

    except ImportError:
        return None


def isAvailable() -> bool:
    """Return True if the cipher backend can be imported."""
    return getCipher('AES') is not None
