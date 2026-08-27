"""Deprecated compatibility imports for the asyncio HLAPI."""

import warnings

warnings.warn(
    'pysnmp.hlapi.asyncore is deprecated; use pysnmp.hlapi.asyncio',
    DeprecationWarning,
    stacklevel=2,
)

from pysnmp.hlapi.asyncio import *
