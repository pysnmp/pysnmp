"""Shared fixtures for integration tests."""

from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest


@pytest.fixture(scope="session")
def snmpsim_endpoint(tmp_path_factory):
    """Start snmpsim on an ephemeral loopback UDP port for the test session."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    data_dir = Path(__file__).parent / "snmpsimdata"
    work_dir = tmp_path_factory.mktemp("snmpsim")
    log_path = work_dir / "snmpsimd.log"
    simulator = Path(sys.executable).with_name("snmpsimd.py")
    if not simulator.is_file():
        pytest.fail("snmpsimd.py was not installed alongside the Python executable")

    with log_path.open("w") as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                str(simulator),
                "--data-dir={}".format(data_dir),
                "--cache-dir={}".format(work_dir / "cache"),
                "--v3-user=00000",
                "--v3-auth-key=authkey1",
                "--v3-auth-proto=MD5",
                "--agent-udpv4-endpoint=127.0.0.1:{}".format(port),
                "--logging-method=stderr",
                "--log-level=info",
            ],
            stdout=subprocess.DEVNULL,
            stderr=log_file,
        )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("snmpsimd.py exited early:\n{}".format(log_path.read_text()))
            if "Listening at UDP/IPv4 endpoint" in log_path.read_text():
                break
            time.sleep(0.05)
        else:
            process.terminate()
            process.wait(timeout=5)
            pytest.fail("snmpsimd.py did not become ready:\n{}".format(log_path.read_text()))

    try:
        yield "127.0.0.1", port
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
