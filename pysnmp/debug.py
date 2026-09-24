#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Debug logging, switched on per subsystem.

`setLogger(Debug('io', 'msgproc'))` turns on tracing for the named areas; the
flags below are the areas. When debugging is off the calls go to `DebugOff`,
which costs a bound-method lookup and nothing else.
"""

import logging

# octs2ints replaced with list() (bytes is already iterable of ints in Python 3)
from pysnmp import __version__, error

flagNone = 0x0000
flagIO = 0x0001
flagDsp = 0x0002
flagMP = 0x0004
flagSM = 0x0008
flagBld = 0x0010
flagMIB = 0x0020
flagIns = 0x0040
flagACL = 0x0080
flagPrx = 0x0100
flagApp = 0x0200
flagAll = 0xFFFF

flagMap = {
    "io": flagIO,
    "dsp": flagDsp,
    "msgproc": flagMP,
    "secmod": flagSM,
    "mibbuild": flagBld,
    "mibview": flagMIB,
    "mibinstrum": flagIns,
    "acl": flagACL,
    "proxy": flagPrx,
    "app": flagApp,
    "all": flagAll,
}


class Printer:
    """Where debug output goes, defaulting to stderr through `logging`."""

    def __init__(self, logger=None, handler=None, formatter=None):
        """Defaults to a stderr handler on the `pysnmp` logger at DEBUG level."""
        if logger is None:
            logger = logging.getLogger("pysnmp")
        logger.setLevel(logging.DEBUG)
        if handler is None:
            handler = logging.StreamHandler()
        if formatter is None:
            formatter = logging.Formatter("%(asctime)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        self.__logger = logger

    def __call__(self, msg):
        """Write one message at DEBUG level."""
        self.__logger.debug(msg)

    def __str__(self):
        """Names the logging backend, for the banner debugging prints on startup."""
        return "<python built-in logging>"


NullHandler = logging.NullHandler


class Debug:
    """Debugging switched on for the named subsystems.

    Truthiness is per flag: `debug.logger & flagIO` is what a caller tests before
    building a message it would otherwise pay to format.
    """

    defaultPrinter = None

    def __init__(self, *flags, **options):
        """Resolve where output goes, then turn on the flags named.

        `printer` wins, then a class-wide default, then `loggerName` -- which attaches
        to an existing logger with a null handler of its own, so output is routed by
        whatever configured that logger rather than to stderr as well.

        An unknown flag name is an error rather than a no-op: a misspelt flag would
        otherwise silently turn nothing on.
        """
        self._flags = flagNone
        if options.get("printer") is not None:
            self._printer = options.get("printer")
        elif self.defaultPrinter is not None:
            self._printer = self.defaultPrinter
        elif "loggerName" in options:
            # route our logs to parent logger
            self._printer = Printer(
                logger=logging.getLogger(options["loggerName"]),
                handler=NullHandler(),
            )
        else:
            self._printer = Printer()
        self(f"running pysnmp version {__version__}")
        for f in flags:
            inverse = f and f[0] in ("!", "~")
            if inverse:
                f = f[1:]
            try:
                if inverse:
                    self._flags &= ~flagMap[f]
                else:
                    self._flags |= flagMap[f]
            except KeyError as exc:
                raise error.PySnmpError(f"bad debug flag {f}") from exc

            self(
                "debug category '{}' {}".format(f, inverse and "disabled" or "enabled")
            )

    def __str__(self):
        """The categories currently switched on."""
        return f"logger {self._printer}, flags {self._flags:x}"

    def __call__(self, msg):
        """Write one message through the printer."""
        self._printer(msg)

    def __and__(self, flag):
        """Whether a category is on, as `debug.logger & flagIO` asks."""
        return self._flags & flag

    def __rand__(self, flag):
        """Whether a category is on, with the operands the other way round."""
        return flag & self._flags


class DebugOff:
    """The stand-in for :class:`Debug` while debugging is switched off.

    The package logs with ``debug.logger & flag and debug.logger(msg)``: the
    bitwise and short-circuits so the message is never built unless the
    category is enabled. That idiom used to run against a plain ``0``, which
    made every one of the 240-odd call sites read as a call to an ``int``.

    This answers the same and with a falsy value and swallows the call that
    never happens, so ``logger`` is one callable type whether debugging is on
    or off. :class:`Debug` cannot fill the role itself -- constructing one
    installs a :class:`Printer` and logs the pysnmp version, which is exactly
    what an unconfigured import must not do.
    """

    def __call__(self, msg):
        """Discard `msg`. Nothing is listening."""

    def __and__(self, flag):
        """Always falsy, so the message after the `and` is never built."""
        return flagNone

    def __rand__(self, flag):
        """Always falsy, with the operands the other way round."""
        return flagNone

    def __bool__(self):
        """Always false."""
        return False

    def __str__(self):
        """Says debugging is off."""
        return "<debugging off>"


#: What `logger` holds until setLogger() installs a Debug instance. Also what
#: setLogger() puts back when it is handed a false value to turn debugging off,
#: which is how `0` -- the historical way to spell that -- keeps working.
DEBUG_OFF = DebugOff()

logger: "Debug | DebugOff" = DEBUG_OFF


def setLogger(newLogger):
    """Install `newLogger` as the debug switch, or turn debugging off.

    Parameters
    ----------
    newLogger:
        A :class:`Debug` instance to log through. Any false value -- ``0``,
        ``None`` -- switches debugging off instead.
    """
    global logger
    logger = newLogger or DEBUG_OFF


def prettify(value):
    """Render a value for debug output.

    ASN.1 objects are rendered with .prettyPrint() -- str() on an OCTET
    STRING decodes the payload as text, which pyasn1 deprecates. Anything
    else falls back to str().
    """
    prettyPrint = getattr(value, "prettyPrint", None)
    if callable(prettyPrint):
        return prettyPrint()
    return str(value)


def hexdump(octets):
    """Octets as hexadecimal, sixteen to a line with the offset at the start."""
    return " ".join(
        [
            "{}{:02X}".format(n % 16 == 0 and f"\n{n:05d}: " or "", x)
            for n, x in zip(range(len(octets)), list(octets))
        ]
    )
