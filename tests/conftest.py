"""Shared fixtures for integration tests."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

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
    simulator = Path(__file__).parent / "snmpsim_launcher.py"
    if not simulator.is_file():
        pytest.fail("snmpsim_launcher.py was not found in tests/")

    repository_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(repository_root), python_path) if path
    )

    import_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib, pysnmp; print(pathlib.Path(pysnmp.__file__).resolve())",
        ],
        cwd=work_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if import_probe.returncode:
        pytest.fail(f"could not import pysnmp in simulator environment:\n{import_probe.stderr}")

    imported_package = Path(import_probe.stdout.strip())
    if not imported_package.is_relative_to(repository_root):
        pytest.fail(f"simulator resolved pysnmp outside this checkout: {imported_package}")

    with log_path.open("w") as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                str(simulator),
                f"--data-dir={data_dir}",
                "--cache-dir={}".format(work_dir / "cache"),
                "--v3-user=00000",
                "--v3-auth-key=authkey1",
                "--v3-auth-proto=MD5",
                f"--agent-udpv4-endpoint=127.0.0.1:{port}",
                "--log-level=info",
            ],
            stdout=subprocess.DEVNULL,
            stderr=log_file,
            env=environment,
        )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"snmpsim exited early:\n{log_path.read_text()}")
            if "Listening at UDP/IPv4 endpoint" in log_path.read_text():
                break
            time.sleep(0.05)
        else:
            process.terminate()
            process.wait(timeout=5)
            pytest.fail(f"snmpsim did not become ready:\n{log_path.read_text()}")

    try:
        yield "127.0.0.1", port
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
