"""The Prism mock server starts on the committed contract and serves its fixture examples."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import yaml

from scripts.mock import PRISM_VERSION, SPEC_PATH, find_npx, prism_command

NPX = find_npx()
# The first run downloads Prism into the npx cache, so allow time for that.
STARTUP_TIMEOUT_S = 300.0

pytestmark = pytest.mark.skipif(NPX is None, reason="npx (Node.js) is not installed")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _stop(proc: subprocess.Popen[bytes]) -> None:
    """Stop npx *and* the node process it spawned."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
    else:
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture(scope="module")
def mock_url() -> Iterator[str]:
    assert NPX is not None
    port = _free_port()
    kwargs: dict[str, Any] = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        prism_command(NPX, port=port),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while True:
            if proc.poll() is not None:
                pytest.fail(f"Prism exited early with code {proc.returncode}")
            try:
                httpx.get(f"{url}/healthz", timeout=2)
                break
            except httpx.TransportError:
                if time.monotonic() > deadline:
                    pytest.fail(f"Prism did not start within {STARTUP_TIMEOUT_S:.0f}s")
                time.sleep(0.5)
        yield url
    finally:
        _stop(proc)


def _spec_example(path: str, method: str, status: str) -> Any:
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    media = spec["paths"][path][method]["responses"][status]["content"]["application/json"]
    examples = media["examples"]
    return next(iter(examples.values()))["value"]


def test_prism_version_is_pinned() -> None:
    parts = PRISM_VERSION.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


def test_mock_serves_property_list_example(mock_url: str) -> None:
    response = httpx.get(f"{mock_url}/v1/properties", timeout=10)
    assert response.status_code == 200
    assert response.json() == _spec_example("/v1/properties", "get", "200")
