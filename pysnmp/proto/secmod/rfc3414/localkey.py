#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""Turning a passphrase into a key, and a key into an engine-local one.

Localizing binds a key to one engine ID, so the same passphrase configured
against two agents yields two different keys and neither can be replayed at
the other.
"""

from hashlib import md5, sha1

from pyasn1.type import univ


def hashPassphrase(passphrase, hashFunc):
    """The password-to-key hash of :RFC:`3414#appendix-A.2`, not yet localized.

    The passphrase is repeated into a ring buffer and exactly one megabyte of it is
    hashed. The cost is the point: it is what makes a short passphrase expensive to
    attack by brute force. The result is not usable as a key until localized.
    """
    passphrase = univ.OctetString(passphrase).asOctets()
    # noinspection PyDeprecation,PyCallingNonCallable
    hasher = hashFunc()
    ringBuffer = passphrase * (64 // len(passphrase) + 1)
    # noinspection PyTypeChecker
    ringBufferLen = len(ringBuffer)
    count = 0
    mark = 0
    while count < 16384:
        e = mark + 64
        if e < ringBufferLen:
            hasher.update(ringBuffer[mark:e])
            mark = e
        else:
            hasher.update(
                ringBuffer[mark:ringBufferLen] + ringBuffer[0 : e - ringBufferLen]
            )
            mark = e - ringBufferLen
        count += 1
    digest = hasher.digest()
    return univ.OctetString(digest)


def passwordToKey(passphrase, snmpEngineId, hashFunc):
    """A passphrase hashed and then localized to `snmpEngineId`, in one step."""
    return localizeKey(hashPassphrase(passphrase, hashFunc), snmpEngineId, hashFunc)


def localizeKey(passKey, snmpEngineId, hashFunc):
    """Bind a key to one engine ID (:RFC:`3414#appendix-A.2`).

    Hashes key, engine ID and key again, so the result cannot be used against any
    other engine. This is what makes a key stolen from one agent useless at the
    next, and also what means a key cannot be re-localized -- the passphrase is
    needed for that.
    """
    passKey = univ.OctetString(passKey).asOctets()
    # noinspection PyDeprecation,PyCallingNonCallable
    digest = hashFunc(passKey + snmpEngineId.asOctets() + passKey).digest()
    return univ.OctetString(digest)


# RFC3414: A.2.1
def hashPassphraseMD5(passphrase):
    """The MD5 password-to-key hash of :RFC:`3414#appendix-A.2.1`."""
    return hashPassphrase(passphrase, md5)


# RFC3414: A.2.2
def hashPassphraseSHA(passphrase):
    """The SHA-1 password-to-key hash of :RFC:`3414#appendix-A.2.2`."""
    return hashPassphrase(passphrase, sha1)


def passwordToKeyMD5(passphrase, snmpEngineId):
    """An MD5 passphrase hashed and localized to `snmpEngineId`."""
    return localizeKey(hashPassphraseMD5(passphrase), snmpEngineId, md5)


def passwordToKeySHA(passphrase, snmpEngineId):
    """A passphrase localized to `snmpEngineId` with SHA-1.

    Does not implement :RFC:`3414#appendix-A.2.2`: the passphrase is hashed with
    MD5 rather than SHA-1 before being localized, so the key this returns does not
    match what another implementation derives from the same passphrase. Nothing in
    pysnmp calls it -- the SHA-1 authentication service uses `hashPassphraseSHA()`
    and `localizeKeySHA()`, which are correct -- and changing it would change the
    keys of anyone who does.
    """
    return localizeKey(hashPassphraseMD5(passphrase), snmpEngineId, sha1)


def localizeKeyMD5(passKey, snmpEngineId):
    """An already-hashed MD5 key bound to `snmpEngineId`."""
    return localizeKey(passKey, snmpEngineId, md5)


def localizeKeySHA(passKey, snmpEngineId):
    """An already-hashed SHA-1 key bound to `snmpEngineId`."""
    return localizeKey(passKey, snmpEngineId, sha1)
