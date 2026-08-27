"""Deprecated compatibility package for the asyncio carrier."""

import warnings

warnings.warn(
    'pysnmp.carrier.asynsock is deprecated; use pysnmp.carrier.asyncio',
    DeprecationWarning,
    stacklevel=2,
)
