#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
# License: https://github.com/pysnmp/pysnmp/blob/main/LICENSE.rst
#
"""The bookkeeping a subtree walk needs, shared by the async and blocking APIs.

GETNEXT and GETBULK are lexicographic over the whole MIB, so deciding when a
walk has left the subtree it was asked for is the caller's job rather than the
protocol's -- and getting it wrong in the obvious ways is what produced the
upstream reports behind this API. It is written once here so that the two
front ends cannot drift apart on it.
"""

from typing import Any

from pyasn1.type.univ import Null

from pysnmp.proto.rfc1905 import endOfMibView

__all__ = ["endColumnsThatLeftTheSubtree", "walkOptions"]


def walkOptions(options: dict[str, Any]) -> tuple[bool, bool, int, int]:
    """Take the walk's own options out of what is passed on to each request.

    `lexicographicMode` is false here, unlike on the single-request primitives:
    a walk is asked for a subtree and stops at the end of it. A caller who wants
    to run on to the end of the MIB says so.
    """
    return (
        options.pop("lexicographicMode", False),
        options.pop("ignoreNonIncreasingOid", False),
        options.pop("maxRows", 0),
        options.pop("maxCalls", 0),
    )


def endColumnsThatLeftTheSubtree(
    rowVarBinds: list[Any],
    previousVarBinds: Any,
    initialVars: list[Any],
    nullVarBinds: list[bool],
    lexicographicMode: bool,
) -> bool:
    """Mark the columns this row has run past the end of, in place.

    A GETNEXT or GETBULK response is lexicographic over the whole MIB, so a
    column runs out when the name comes back outside the subtree it started in,
    or when the agent says so with an exception value. Either way the binding is
    replaced with the previous name and `endOfMibView`, which is what a caller
    reads to see that column is done.

    `nullVarBinds` remembers the columns already finished, so that a GETBULK
    response whose later rows carry values for a column that ended in an earlier
    one does not appear to revive it.

    Returns
    -------
        Whether every column in this row has now ended, which is what ends the
        walk.
    """
    for column, (name, value) in enumerate(rowVarBinds):
        if (
            nullVarBinds[column]
            or isinstance(value, Null)
            or (not lexicographicMode and not initialVars[column].isPrefixOf(name))
        ):
            rowVarBinds[column] = previousVarBinds[column][0], endOfMibView
            nullVarBinds[column] = True

    return all(value is endOfMibView for _, value in rowVarBinds)
