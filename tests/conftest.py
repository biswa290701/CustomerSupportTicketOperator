"""Shared pytest fixtures.

Two levels of testing are provided:

* ``client``   - FastAPI's TestClient (in-process, no browser) used for the
                 database and filtering tests.
* ``operator`` - a real uvicorn process plus a Chromium browser, used for the
                 browser-operator tests.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """An isolated SQLite file path (does not exist yet)."""
    return tmp_path / "tickets.db"


@pytest.fixture
def client(temp_db: Path, monkeypatch: pytest.MonkeyPatch):
    """In-process app instance backed by a throw-away database."""
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("TICKET_DB_PATH", str(temp_db))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def live_server(temp_db: Path):
    """Start a real uvicorn server with a throw-away database."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["TICKET_DB_PATH"] = str(temp_db)
    env["APP_PORT"] = str(port)

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    deadline = time.time() + 45
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read().decode(errors="replace") if process.stdout else ""
            raise RuntimeError(f"uvicorn exited early:\n{output}")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.3)
    else:
        process.terminate()
        raise RuntimeError("uvicorn did not become healthy within 45s")

    yield base_url

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@pytest.fixture
def operator(live_server: str):
    """A started Playwright operator pointed at the live server."""
    pytest.importorskip("playwright.sync_api")

    from browser_operator.browser_operator import TicketOperator

    # Screenshots / logs go to the project evidence folder (git-ignored).
    with TicketOperator(live_server, headless=True) as ticket_operator:
        yield ticket_operator
