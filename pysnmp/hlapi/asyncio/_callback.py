#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Internal callback helpers for the asyncio HLAPI."""

from collections.abc import Callable
from typing import Any


def make_callback(
    unmake_fn: Callable[..., Any],
    *,
    multi_row: bool = False,
) -> Callable[..., None]:
    """Build the callback used by asyncio command generators."""

    def _cb_fun(  # pylint: disable=too-many-positional-arguments
        snmpEngine: Any,
        sendRequestHandle: Any,
        errorIndication: Any,
        errorStatus: Any,
        errorIndex: Any,
        varBinds: Any,
        cbCtx: Any,
    ) -> None:
        lookupMib, future = cbCtx
        if future.cancelled():
            return

        try:
            if multi_row:
                varBindsUnmade = [
                    unmake_fn(snmpEngine, varBindTableRow, lookupMib)
                    for varBindTableRow in varBinds
                ]
            else:
                varBindsUnmade = unmake_fn(snmpEngine, varBinds, lookupMib)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            future.set_exception(ex)
        else:
            future.set_result((errorIndication, errorStatus, errorIndex, varBindsUnmade))

    return _cb_fun
