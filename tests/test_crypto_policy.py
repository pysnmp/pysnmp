"""Tests for the cipher backend indirection and weak-crypto configuration warnings."""

import subprocess
import sys
import warnings

import pytest

from pysnmp.entity import config, engine
from pysnmp.error import (
    PySnmpCryptoWarning,
    PySnmpError,
    PySnmpNonStandardCryptoWarning,
    PySnmpWeakCryptoWarning,
)
from pysnmp.proto.secmod import cipherbackend

AUTH_KEY = 'authkey12345'
PRIV_KEY = 'privkey12345'


@pytest.fixture
def snmpEngine():
    return engine.SnmpEngine()


def addUser(snmpEngine, userName, **kwargs):
    config.addV3User(snmpEngine, userName, **kwargs)


class TestCipherBackend:
    def test_ciphers_resolve(self):
        for name in ('AES', 'DES', 'DES3'):
            assert cipherbackend.getCipher(name) is not None

    def test_unknown_cipher_is_none(self):
        assert cipherbackend.getCipher('NoSuchCipher') is None

    def test_is_available(self):
        assert cipherbackend.isAvailable() is True

    def test_result_is_cached(self):
        assert cipherbackend.getCipher('AES') is cipherbackend.getCipher('AES')


class TestWeakProtocolWarnings:
    @pytest.mark.parametrize(
        'privProtocol',
        [config.usmDESPrivProtocol, config.usm3DESEDEPrivProtocol],
        ids=['des', '3des'],
    )
    def test_weak_priv_protocol_warns(self, snmpEngine, privProtocol):
        with pytest.warns(PySnmpWeakCryptoWarning):
            addUser(
                snmpEngine,
                'weak-priv',
                authProtocol=config.usmHMAC192SHA256AuthProtocol,
                authKey=AUTH_KEY,
                privProtocol=privProtocol,
                privKey=PRIV_KEY,
            )

    def test_weak_auth_protocol_warns(self, snmpEngine):
        with pytest.warns(PySnmpWeakCryptoWarning, match='RFC 6151'):
            addUser(
                snmpEngine,
                'weak-auth',
                authProtocol=config.usmHMACMD5AuthProtocol,
                authKey=AUTH_KEY,
            )

    def test_warning_names_a_replacement(self, snmpEngine):
        with pytest.warns(PySnmpWeakCryptoWarning, match='usmAesCfb128Protocol'):
            addUser(
                snmpEngine,
                'des-user',
                authProtocol=config.usmHMAC192SHA256AuthProtocol,
                authKey=AUTH_KEY,
                privProtocol=config.usmDESPrivProtocol,
                privKey=PRIV_KEY,
            )

    @pytest.mark.parametrize(
        'privProtocol',
        [
            config.usmAesCfb192Protocol,
            config.usmAesCfb256Protocol,
            config.usmAesBlumenthalCfb192Protocol,
            config.usmAesBlumenthalCfb256Protocol,
        ],
        ids=['reeder192', 'reeder256', 'blumenthal192', 'blumenthal256'],
    )
    def test_non_standard_protocol_warns(self, snmpEngine, privProtocol):
        with pytest.warns(PySnmpNonStandardCryptoWarning, match='expired IETF draft'):
            addUser(
                snmpEngine,
                'non-standard',
                authProtocol=config.usmHMAC192SHA256AuthProtocol,
                authKey=AUTH_KEY,
                privProtocol=privProtocol,
                privKey=PRIV_KEY,
            )

    def test_warning_categories_share_a_base(self):
        assert issubclass(PySnmpWeakCryptoWarning, PySnmpCryptoWarning)
        assert issubclass(PySnmpNonStandardCryptoWarning, PySnmpCryptoWarning)

    def test_warnings_visible_under_default_filters(self):
        assert issubclass(PySnmpCryptoWarning, UserWarning)


class TestSafeProtocolsAreSilent:
    @pytest.mark.parametrize(
        'authProtocol',
        [
            config.usmHMACSHAAuthProtocol,
            config.usmHMAC128SHA224AuthProtocol,
            config.usmHMAC192SHA256AuthProtocol,
            config.usmHMAC256SHA384AuthProtocol,
            config.usmHMAC384SHA512AuthProtocol,
        ],
        ids=['sha1', 'sha224', 'sha256', 'sha384', 'sha512'],
    )
    def test_recommended_combinations_do_not_warn(self, snmpEngine, authProtocol):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            addUser(
                snmpEngine,
                'safe',
                authProtocol=authProtocol,
                authKey=AUTH_KEY,
                privProtocol=config.usmAesCfb128Protocol,
                privKey=PRIV_KEY,
            )

        assert [w for w in caught if issubclass(w.category, PySnmpCryptoWarning)] == []

    def test_no_auth_no_priv_does_not_warn(self, snmpEngine):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            addUser(snmpEngine, 'noauth')

        assert [w for w in caught if issubclass(w.category, PySnmpCryptoWarning)] == []


class TestUnknownProtocols:
    def test_unknown_priv_protocol_rejected(self, snmpEngine):
        with pytest.raises(PySnmpError, match='Unknown privacy protocol'):
            addUser(snmpEngine, 'unknown-priv', privProtocol=(1, 3, 6, 1, 4, 1, 99999))

    def test_unknown_auth_protocol_rejected(self, snmpEngine):
        with pytest.raises(PySnmpError, match='Unknown auth protocol'):
            addUser(snmpEngine, 'unknown-auth', authProtocol=(1, 3, 6, 1, 4, 1, 99999))


class TestMissingBackend:
    def test_unknown_protocol_precedes_backend_error(self, snmpEngine, monkeypatch):
        monkeypatch.setattr(cipherbackend, 'isAvailable', lambda: False)

        with pytest.raises(PySnmpError, match='Unknown privacy protocol'):
            addUser(snmpEngine, 'unknown-priv', privProtocol=(1, 3, 6, 1, 4, 1, 99999))

    def test_priv_config_raises_actionable_error(self, snmpEngine, monkeypatch):
        monkeypatch.setattr(cipherbackend, 'isAvailable', lambda: False)

        with pytest.raises(PySnmpError, match='pycryptodomex'):
            addUser(
                snmpEngine,
                'priv',
                authProtocol=config.usmHMAC192SHA256AuthProtocol,
                authKey=AUTH_KEY,
                privProtocol=config.usmAesCfb128Protocol,
                privKey=PRIV_KEY,
            )

    def test_auth_only_config_still_works(self, snmpEngine, monkeypatch):
        monkeypatch.setattr(cipherbackend, 'isAvailable', lambda: False)

        addUser(
            snmpEngine,
            'authonly',
            authProtocol=config.usmHMAC192SHA256AuthProtocol,
            authKey=AUTH_KEY,
        )


# Without pycryptodomex importable at all, pysnmp must still import and serve
# SNMPv1, SNMPv2c and the SNMPv3 noAuthNoPriv/authNoPriv security levels.
WITHOUT_PYCRYPTODOMEX = """
import sys


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name == 'Cryptodome' or name.startswith('Cryptodome.'):
            raise ImportError('blocked')
        return None


sys.meta_path.insert(0, Blocker())

from pysnmp.entity import config, engine
from pysnmp.hlapi.asyncio import *

snmpEngine = engine.SnmpEngine()
config.addV1System(snmpEngine, 'my-area', 'public')
config.addV3User(
    snmpEngine, 'authonly',
    authProtocol=config.usmHMAC192SHA256AuthProtocol, authKey='authkey12345',
)

try:
    config.addV3User(
        snmpEngine, 'priv',
        authProtocol=config.usmHMAC192SHA256AuthProtocol, authKey='authkey12345',
        privProtocol=config.usmAesCfb128Protocol, privKey='privkey12345',
    )
except Exception as exc:
    assert 'pycryptodomex' in str(exc), exc
else:
    raise AssertionError('expected privacy configuration to fail')

print('OK')
"""


def test_usable_without_pycryptodomex_installed():
    result = subprocess.run(
        [sys.executable, '-c', WITHOUT_PYCRYPTODOMEX],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout
