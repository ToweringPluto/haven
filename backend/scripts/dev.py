"""Run the whole app locally: the FastAPI backend (:8000) and the Vite frontend (:5173).

The frontend's Vite dev server proxies ``/v1`` to the backend, so open
http://localhost:5173. Ctrl+C stops both; if either server exits, the other is stopped too.
Installs the frontend's npm packages first if ``frontend/node_modules`` is missing.

Usage (from the repo root)::

    uv run --directory backend poe dev
"""

from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
BACKEND_PORT = 8000
FRONTEND_URL = "http://localhost:5173"


def find_npm() -> str | None:
    """Full path to npm (``npm.cmd`` on Windows, where the bare shim can't be spawned)."""
    if sys.platform == "win32":
        return shutil.which("npm.cmd") or shutil.which("npm.exe")
    return shutil.which("npm")


def backend_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "haven.api.app:create_app",
        "--factory",
        "--reload",
        "--port",
        str(BACKEND_PORT),
    ]


def frontend_command(npm: str) -> list[str]:
    return [npm, "run", "dev"]


def stop(proc: subprocess.Popen[bytes]) -> None:
    """Stop a server and its children (npm and uvicorn --reload both spawn child processes)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    npm = find_npm()
    if npm is None:
        print("npm not found: install Node.js to run the frontend", file=sys.stderr)
        return 1
    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("Installing frontend packages (npm ci)...")
        if subprocess.call([npm, "ci", "--no-audit", "--no-fund"], cwd=FRONTEND_DIR) != 0:
            return 1

    procs = [
        subprocess.Popen(backend_command(), cwd=BACKEND_DIR),
        subprocess.Popen(frontend_command(npm), cwd=FRONTEND_DIR),
    ]
    print(f"\nHaven is starting: open {FRONTEND_URL}  (API docs: http://localhost:8000/docs)")
    print("Press Ctrl+C to stop both servers.\n")
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        print("A server exited; stopping the other one.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for p in procs:
            stop(p)


if __name__ == "__main__":
    sys.exit(main())
