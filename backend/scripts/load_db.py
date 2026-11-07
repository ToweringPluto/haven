"""Load the data layer into the database (Tiger Cloud / TimescaleDB).

Needs ``HAVEN_DATABASE_URL`` (see ``backend/.env.example``). Applies
``data/sql/rent_stats.sql``: creates the ``rent_stats`` hypertable if needed and upserts the
Lothian rent series. Safe to run repeatedly.

Usage (from ``backend/``)::

    uv run python scripts/load_db.py --ping   # check the connection only
    uv run python scripts/load_db.py          # create/upsert rent_stats
"""

from __future__ import annotations

import argparse
import sys

from haven.datasets.db import load_rent_stats
from haven.store.db import DatabaseNotConfiguredError, ping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ping", action="store_true", help="check the connection only")
    args = parser.parse_args(argv)
    try:
        print(f"connected: {ping()}")
        if args.ping:
            return 0
        print(f"rent_stats: {load_rent_stats()} rows")
    except DatabaseNotConfiguredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
