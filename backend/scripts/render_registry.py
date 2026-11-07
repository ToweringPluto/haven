"""Render ``data/datasets.yml`` into the README's dataset table.

Usage (from ``backend/``)::

    uv run python scripts/render_registry.py          # rewrite the table in README.md
    uv run python scripts/render_registry.py --check  # fail if the table is stale
"""

from __future__ import annotations

import argparse
import sys

from haven.config import REPO_ROOT
from haven.datasets import load_registry
from haven.datasets.registry import render_markdown_table, replace_table

README = REPO_ROOT / "README.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = README.read_text(encoding="utf-8")
    updated = replace_table(text, render_markdown_table(load_registry()))
    if updated == text:
        print("README dataset table is up to date")
        return 0
    if args.check:
        print("README dataset table is stale; run scripts/render_registry.py", file=sys.stderr)
        return 1
    README.write_text(updated, encoding="utf-8", newline="\n")
    print(f"updated {README}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
