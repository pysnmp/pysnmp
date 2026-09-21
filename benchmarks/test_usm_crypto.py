#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
"""Benchmarks for the USM (:RFC:`3414`) authentication and privacy services.

Key derivation runs once per configured user, while the digest and cipher
services run on every single SNMPv3 message that goes over the wire.
"""
import pytest

from pyasn1.type import univ

from pysnmp.proto.secmod.rfc3414 import localkey
from pysnmp.proto.secmod.rfc3414.auth import hmacmd5, hmacsha
from pysnmp.proto.secmod.rfc3414.priv import des
from pysnmp.proto.secmod.rfc3826.priv import aes
from pysnmp.proto.secmod.rfc7860.auth import hmacsha2

from payloads import SNMP_ENGINE_ID

PASSPHRASE = 'thats-not-a-very-good-passphrase'

# A ~1 kB scoped PDU, the typical size of a bulk response payload.
SCOPED_PDU = univ.OctetString(b'\x30\x82\x03\xf0' + b'\xa5' * 1020).asOctets()


def _whole_msg(digestLength):
    """An outgoing message with a zeroed-out digest placeholder in it."""
    return b'\x30\x82\x04\x20' + b'\x00' * digestLength + b'\xa5' * 1024


@pytest.fixture(scope='module')
def md5_key():
    return localkey.passwordToKeyMD5(PASSPHRASE, SNMP_ENGINE_ID)


@pytest.fixture(scope='module')
def sha_key():
    return localkey.passwordToKeySHA(PASSPHRASE, SNMP_ENGINE_ID)


def test_password_to_key_md5(benchmark):
    """Key derivation hashes 1 MB of key material, per :RFC:`3414` A.2.1."""
    benchmark(localkey.passwordToKeyMD5, PASSPHRASE, SNMP_ENGINE_ID)


def test_password_to_key_sha(benchmark):
    benchmark(localkey.passwordToKeySHA, PASSPHRASE, SNMP_ENGINE_ID)


def test_localize_key_md5(benchmark):
    passKey = localkey.hashPassphraseMD5(PASSPHRASE)

    benchmark(localkey.localizeKeyMD5, passKey, SNMP_ENGINE_ID)


def test_hmac_md5_authenticate_outgoing(benchmark, md5_key):
    service = hmacmd5.HmacMd5()
    wholeMsg = _whole_msg(service.digestLength)

    @benchmark
    def _():
        for _unused in range(16):
            service.authenticateOutgoingMsg(md5_key, wholeMsg)


def test_hmac_sha_authenticate_outgoing(benchmark, sha_key):
    service = hmacsha.HmacSha()
    wholeMsg = _whole_msg(service.digestLength)

    @benchmark
    def _():
        for _unused in range(16):
            service.authenticateOutgoingMsg(sha_key, wholeMsg)


def test_hmac_sha256_authenticate_outgoing(benchmark):
    service = hmacsha2.HmacSha2(hmacsha2.HmacSha2.sha256ServiceID)
    authKey = service.localizeKey(
        service.hashPassphrase(univ.OctetString(PASSPHRASE)), SNMP_ENGINE_ID
    )
    wholeMsg = _whole_msg(service.digestLength)

    @benchmark
    def _():
        for _unused in range(16):
            service.authenticateOutgoingMsg(authKey, wholeMsg)


def test_hmac_md5_authenticate_incoming(benchmark, md5_key):
    service = hmacmd5.HmacMd5()
    authenticatedMsg = service.authenticateOutgoingMsg(
        md5_key, _whole_msg(service.digestLength)
    )
    authParameters = univ.OctetString(authenticatedMsg[4:4 + service.digestLength])

    @benchmark
    def _():
        for _unused in range(16):
            service.authenticateIncomingMsg(
                md5_key, authParameters, authenticatedMsg
            )


def test_des_encrypt(benchmark, md5_key):
    service = des.Des()

    @benchmark
    def _():
        for _unused in range(16):
            service.encryptData(md5_key, (1, 42, None), SCOPED_PDU)


def test_des_decrypt(benchmark, md5_key):
    service = des.Des()
    cipherText, salt = service.encryptData(md5_key, (1, 42, None), SCOPED_PDU)

    @benchmark
    def _():
        for _unused in range(16):
            service.decryptData(md5_key, (1, 42, salt), cipherText)


def test_aes_encrypt(benchmark):
    service = aes.Aes()
    privKey = service.localizeKey(
        hmacmd5.HmacMd5.serviceID, univ.OctetString(PASSPHRASE), SNMP_ENGINE_ID
    )

    @benchmark
    def _():
        for _unused in range(16):
            service.encryptData(privKey, (1, 42, None), SCOPED_PDU)


def test_aes_decrypt(benchmark):
    service = aes.Aes()
    privKey = service.localizeKey(
        hmacmd5.HmacMd5.serviceID, univ.OctetString(PASSPHRASE), SNMP_ENGINE_ID
    )
    cipherText, salt = service.encryptData(privKey, (1, 42, None), SCOPED_PDU)

    @benchmark
    def _():
        for _unused in range(16):
            service.decryptData(privKey, (1, 42, salt), cipherText)
