"""Deprecated compatibility package for the asyncio carrier."""

import warnings

warnings.warn(
    'pysnmp.carrier.asyncore is deprecated; use pysnmp.carrier.asyncio',
    DeprecationWarning,
    stacklevel=2,
)
