"""Integration tests for SNMPv3 auth/priv combinations against local snmpsim.

Tests the full matrix of authentication and privacy protocols to reproduce
and verify fixes for issue #54.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pysnmp.hlapi import (
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    usmAesBlumenthalCfb192Protocol,
    usmAesBlumenthalCfb256Protocol,
    usmAesCfb128Protocol,
    usmAesCfb192Protocol,
    usmAesCfb256Protocol,
    usmDESPrivProtocol,
    usmHMAC128SHA224AuthProtocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
    usmNoPrivProtocol,
)

SYS_DESCR = "1.3.6.1.2.1.1.1.0"

# Auth protocol OID → (snmpsim proto name, hlapi constant, auth key)
AUTH_MATRIX = {
    "MD5": ("MD5", usmHMACMD5AuthProtocol, "authkey1"),
    "SHA": ("SHA", usmHMACSHAAuthProtocol, "authkey1"),
    "SHA224": ("SHA224", usmHMAC128SHA224AuthProtocol, "authkey1"),
    "SHA256": ("SHA256", usmHMAC192SHA256AuthProtocol, "authkey1"),
    "SHA384": ("SHA384", usmHMAC256SHA384AuthProtocol, "authkey1"),
    "SHA512": ("SHA512", usmHMAC384SHA512AuthProtocol, "authkey1"),
}

# Priv protocol OID → (snmpsim proto name, hlapi constant, priv key)
PRIV_MATRIX = {
    "None": (None, usmNoPrivProtocol, None),
    "DES": ("DES", usmDESPrivProtocol, "privkey1"),
    "AES128": ("AES", usmAesCfb128Protocol, "privkey1"),
    "AES192": ("AES192", usmAesCfb192Protocol, "privkey1"),
    "AES192B": ("AES192BLMT", usmAesBlumenthalCfb192Protocol, "privkey1"),
    "AES256": ("AES256", usmAesCfb256Protocol, "privkey1"),
    "AES256B": ("AES256BLMT", usmAesBlumenthalCfb256Protocol, "privkey1"),
}


def _start_snmpsim(tmp_path, auth_proto, priv_proto, auth_key, priv_key):
    """Start a snmpsim instance with the given v3 user configuration."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    data_dir = Path(__file__).parent / "snmpsimdata"
    work_dir = tmp_path / "snmpsim"
    work_dir.mkdir(parents=True, exist_ok=True)
    log_path = work_dir / "snmpsimd.log"
    simulator = Path(__file__).parent / "snmpsim_launcher.py"
    if not simulator.is_file():
        pytest.fail("snmpsim_launcher.py was not found in tests/")

    repository_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(repository_root), python_path) if path
    )

    cmd = [
        sys.executable,
        str(simulator),
        f"--data-dir={data_dir}",
        "--cache-dir={}".format(work_dir / "cache"),
        "--v3-user=testuser",
        f"--agent-udpv4-endpoint=127.0.0.1:{port}",
        "--log-level=info",
    ]

    if auth_proto:
        cmd += [f"--v3-auth-key={auth_key}", f"--v3-auth-proto={auth_proto}"]
    if priv_proto:
        cmd += [f"--v3-priv-key={priv_key}", f"--v3-priv-proto={priv_proto}"]

    with log_path.open("w") as log_file:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=log_file,
            env=environment,
        )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                log_content = log_path.read_text()
                pytest.fail(f"snmpsim exited early:\n{log_content}")
            if "Listening at UDP/IPv4 endpoint" in log_path.read_text():
                break
            time.sleep(0.05)
        else:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            log_content = log_path.read_text()
            pytest.fail(f"snmpsim did not become ready:\n{log_content}")

    return ("127.0.0.1", port), process, log_path


def _do_get(host, port, auth_proto_oid, auth_key, priv_proto_oid, priv_key):
    """Perform an SNMPv3 GET and return the result."""
    return next(
        getCmd(
            SnmpEngine(),
            UsmUserData(
                "testuser",
                authKey=auth_key,
                privKey=priv_key,
                authProtocol=auth_proto_oid,
                privProtocol=priv_proto_oid,
            ),
            UdpTransportTarget((host, port), timeout=2, retries=1),
            ContextData(contextName="testuser"),
            ObjectType(ObjectIdentity(SYS_DESCR)),
        )
    )


def _get_value(result):
    error_indication, error_status, error_index, var_binds = result
    assert error_indication is None, f"errorIndication: {error_indication}"
    assert not error_status, f"errorStatus: {error_status} at index {error_index}"
    return var_binds[0][1].prettyPrint()


# --- Individual combination tests ---


class TestAuthPrivMatrix:
    """Test every auth/priv combination against a local snmpsim instance."""

    @pytest.fixture(autouse=True)
    def _start_simulator(self, request, tmp_path):
        auth_name = request.param[0]
        priv_name = request.param[1]
        auth_proto, auth_oid, auth_key = AUTH_MATRIX[auth_name]
        priv_proto, priv_oid, priv_key = PRIV_MATRIX[priv_name]

        endpoint, process, log_path = _start_snmpsim(
            tmp_path, auth_proto, priv_proto, auth_key, priv_key
        )
        self._endpoint = endpoint
        self._process = process
        self._log_path = log_path
        self._auth_oid = auth_oid
        self._auth_key = auth_key
        self._priv_oid = priv_oid
        self._priv_key = priv_key
        yield
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    @pytest.mark.parametrize(
        "_start_simulator",
        [
            (auth, priv)
            for auth in AUTH_MATRIX
            for priv in PRIV_MATRIX
            if not (auth == "None" and priv != "None")  # priv requires auth
        ],
        indirect=True,
        ids=[
            f"{auth}-{priv}"
            for auth in AUTH_MATRIX
            for priv in PRIV_MATRIX
            if not (auth == "None" and priv != "None")
        ],
    )
    def test_get(self):
        host, port = self._endpoint
        result = _do_get(
            host,
            port,
            self._auth_oid,
            self._auth_key,
            self._priv_oid,
            self._priv_key,
        )
        value = _get_value(result)
        assert "pysnmp integration" in value.lower(), (
            f"Unexpected response for {self._auth_oid}/{self._priv_oid}: {value}\n"
            f"snmpsim log: {self._log_path.read_text()[-500:] if self._log_path.exists() else 'N/A'}"
        )
