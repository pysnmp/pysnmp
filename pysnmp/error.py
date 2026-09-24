#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""The exception and warning types every other pysnmp module raises."""


class PySnmpCryptoWarning(UserWarning):
    """Base class for warnings about SNMPv3 cryptographic protocol selection.

    Subclasses of this warning are raised at user configuration time rather
    than at packet processing time. They derive from `UserWarning` (not
    `DeprecationWarning`) so that they remain visible under Python's default
    warning filters, since ignoring them has security consequences.
    """


class PySnmpWeakCryptoWarning(PySnmpCryptoWarning):
    """The selected protocol is no longer considered cryptographically safe."""


class PySnmpNonStandardCryptoWarning(PySnmpCryptoWarning):
    """The selected protocol is not standards-track and may not interoperate."""


class PySnmpShadowedModuleWarning(UserWarning):
    """A MIB module is present in more than one source, and one copy was chosen.

    Raised while enumerating sources rather than while decoding, because that
    is where the configuration that caused it can still be changed. Derived
    from `UserWarning` for the same reason the crypto warnings are: a
    deployment carrying two copies of a MIB is resolving every OID in it
    against whichever copy won, and that is worth seeing under the default
    filters.

    Which copy won is stated, never whether the copies differ -- answering
    that means loading and normalizing both, which is the work a corpus
    exists to avoid.
    """


class PySnmpError(Exception):
    """Base class for pysnmp exceptions.

    Carries the exception it was raised from, if any, into its own string
    form, so a caller that only logs `str(exc)` still sees the underlying
    failure.
    """

    @property
    def _chained(self) -> BaseException | None:
        return self.__cause__ or self.__context__

    @property
    def cause(self) -> tuple:
        """The chained exception as a `sys.exc_info()`-shaped triple.

        Empty triple when this exception was not raised while another was
        being handled.
        """
        cause = self._chained
        if cause is None:
            return (None, None, None)
        return (type(cause), cause, cause.__traceback__)

    def __str__(self) -> str:
        """The message, with the exception this was raised from appended."""
        msg = super().__str__()
        cause = self._chained
        if cause is None:
            return msg
        suffix = f"caused by {type(cause).__name__}: {cause}"
        return f"{msg}, {suffix}" if msg else suffix
