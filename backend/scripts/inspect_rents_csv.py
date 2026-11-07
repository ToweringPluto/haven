"""Inspect the Private Rents Open Data CSV before loading it.

Prints the header, row count, the distinct values of every low-cardinality column and the
years present for Lothian, so a change in column names or categories between releases is
caught before ``build_seeds.py`` loads the file into ``rent_stats``.

Usage (from ``backend/``)::

    uv run python scripts/inspect_rents_csv.py            # inspect data/raw/rents/*.csv
    uv run python scripts/inspect_rents_csv.py --download # fetch the CSV first if missing
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import defaultdict

from haven.datasets.loaders import rents


def inspect(text: str) -> int:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    rows = [r for r in reader if r]
    print(f"header: {header}")
    print(f"rows:   {len(rows)}")
    if header is None:
        print("error: empty file", file=sys.stderr)
        return 1
    distinct: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for name, value in zip(header, row, strict=False):
            distinct[name].add(value.strip())
    for name in header:
        values = distinct[name]
        shown = sorted(values) if len(values) <= 25 else f"{len(values)} distinct values"
        print(f"  {name}: {shown}")
    if header != rents.EXPECTED_HEADER:
        print(
            f"error: header differs from the loader's expected {rents.EXPECTED_HEADER}; "
            "update haven/datasets/loaders/rents.py before loading",
            file=sys.stderr,
        )
        return 1
    years = sorted({r[1] for r in rows if r[0].strip() == rents.BRMA})
    print(f"{rents.BRMA} years: {years}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="fetch the CSV if missing")
    args = parser.parse_args(argv)
    if args.download:
        rents.download()
    if not rents.RAW_CSV.is_file():
        print(f"error: {rents.RAW_CSV} not found (run with --download)", file=sys.stderr)
        return 1
    return inspect(rents.RAW_CSV.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    raise SystemExit(main())
