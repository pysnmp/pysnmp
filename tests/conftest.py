"""Shared fixtures for integration tests."""

import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

#: The test modules that build a MIB corpus, and so drive pysmi's corpus
#: writer.
#:
#: That writer commits SQLite while a statement is still open
#: (``pysmi/corpus/db.py``, ``write_db``). CPython's ``sqlite3`` tolerates it,
#: because the implicit cursor behind ``Connection.execute`` is released as its
#: last reference goes and the statement resets with it. PyPy's does not -- it
#: collects that cursor later, and the commit meets "cannot commit transaction
#: - SQL statements in progress". Every one of these modules errors there, and
#: nothing in pysnmp can make them pass.
#:
#: So they are skipped where the interpreter is not CPython, and only they: the
#: rest of the suite runs, and a PyPy failure anywhere else is a real one that
#: the matrix is there to catch. Delete this the day pysmi closes its cursors.
CORPUS_WRITER_MODULES = frozenset(
    {
        "test_behavior.py",
        "test_corpus.py",
        "test_generated_mibs.py",
        "test_precedence.py",
        "test_provenance.py",
    }
)


def pytest_collection_modifyitems(config, items):
    """Skip the corpus-writer tests on an interpreter whose sqlite3 refuses them."""
    if platform.python_implementation() == "CPython":
        return

    skip = pytest.mark.skip(
        reason=(
            "pysmi's corpus writer commits SQLite with a statement still open, "
            f"which {platform.python_implementation()}'s sqlite3 refuses"
        )
    )
    for item in items:
        if Path(str(item.fspath)).name in CORPUS_WRITER_MODULES:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def _snmpsim_process(tmp_path_factory):
    """Start snmpsim on ephemeral loopback UDP and TCP ports for the session.

    One simulator serves both, so a TCP test costs no second process. It yields
    both ports; `snmpsim_endpoint` and `snmpsim_tcp_endpoint` pick one each.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        tcp_port = sock.getsockname()[1]

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
        pytest.fail(
            f"could not import pysnmp in simulator environment:\n{import_probe.stderr}"
        )

    imported_package = Path(import_probe.stdout.strip())
    if not imported_package.is_relative_to(repository_root):
        pytest.fail(
            f"simulator resolved pysnmp outside this checkout: {imported_package}"
        )

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
                f"--agent-tcpv4-endpoint=127.0.0.1:{tcp_port}",
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
            if "Listening at TCP/IPv4 endpoint" in log_path.read_text():
                break
            time.sleep(0.05)
        else:
            process.terminate()
            process.wait(timeout=5)
            pytest.fail(f"snmpsim did not become ready:\n{log_path.read_text()}")

    try:
        yield port, tcp_port
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture(scope="session")
def snmpsim_endpoint(_snmpsim_process):
    """Where the simulator answers over UDP."""
    port, _ = _snmpsim_process
    return "127.0.0.1", port


@pytest.fixture(scope="session")
def snmpsim_tcp_endpoint(_snmpsim_process):
    """Where the simulator answers over TCP (:RFC:`3430`)."""
    _, tcp_port = _snmpsim_process
    return "127.0.0.1", tcp_port
