"""Run the Stoplight Prism mock server on the committed contract (for the frontend team).

Prism serves the examples embedded in ``contracts/openapi.yaml`` (the persona fixtures), so
every response is illustrative fixture data, not real engine output. Prism is pinned and run
through ``npx`` (Node is the only requirement; nothing is installed globally).

Usage (from ``backend/``)::

    uv run poe mock                          # http://127.0.0.1:4010/v1/properties
    uv run python scripts/mock.py --port 4020
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PRISM_VERSION = "5.16.0"
PRISM_PACKAGE = f"@stoplight/prism-cli@{PRISM_VERSION}"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4010
SPEC_PATH = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"


def find_npx() -> str | None:
    """Full path to npx (``npx.cmd`` on Windows), or None when Node isn't installed.

    On Windows, ``shutil.which("npx")`` can return Node's extensionless POSIX shell shim,
    which ``CreateProcess`` can't run, so look for ``npx.cmd`` first.
    """
    if sys.platform == "win32":
        return shutil.which("npx.cmd") or shutil.which("npx.exe")
    return shutil.which("npx")


def prism_command(npx: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> list[str]:
    return [
        npx,
        "--yes",
        PRISM_PACKAGE,
        "mock",
        str(SPEC_PATH),
        "--host",
        host,
        "--port",
        str(port),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    npx = find_npx()
    if npx is None:
        print("npx not found: install Node.js to run the Prism mock server", file=sys.stderr)
        return 1
    try:
        return subprocess.call(prism_command(npx, args.host, args.port))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
