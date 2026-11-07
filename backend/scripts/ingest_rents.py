"""Build ``data/reference/rents_lothian_brma.yaml`` from the Private Rents Open Data CSV.

The Scottish Government's "Private Sector Rent Statistics, Scotland, 2010 to 2025" (published
25 November 2025) ships an open data CSV with columns ``BRMA, Year, Measure, Beds, Value``: one
row per Broad Rental Market Area, statistics year (to end September), measure (Lower Quartile,
Median, Mean, Upper Quartile, Number of Records) and bedroom category. This script keeps the
**Lothian** rows for the **latest year** in the file and writes them, with provenance, to the
YAML reference file. Every measure must be present and numeric; a missing value is an error,
never a default.

Usage (from ``backend/``)::

    uv run python scripts/ingest_rents.py --download  # fetch the CSV if missing, then ingest
    uv run python scripts/ingest_rents.py             # ingest the CSV in data/raw/rents/
    uv run python scripts/ingest_rents.py --check     # validate the YAML; if the CSV is
                                                      # present, re-parse and compare

The raw CSV lives in ``data/raw/rents/`` (gitignored).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from haven.config import REFERENCE_DIR, REPO_ROOT
from haven.reference import load_reference_file
from haven.reference.rents import FILE_NAME, RentReference

RAW_DIR = REPO_ROOT / "data" / "raw" / "rents"
RAW_CSV = RAW_DIR / "private_rents_open_data_2010_2025.csv"
OUTPUT = REFERENCE_DIR / f"{FILE_NAME}.yaml"
USER_AGENT = "haven-prototype"

_PUB = (
    "https://www.gov.scot/binaries/content/documents/govscot/publications/statistics/2025/11/"
    "private-sector-rent-statistics-scotland-2010-to-2025/documents/"
)
SOURCE_URL = (
    _PUB + "prs-rent-statistics-2025---private-rents-open-data/"
    "prs-rent-statistics-2025---private-rents-open-data/govscot%3Adocument/"
    "Private%2BSector%2BRent%2BStatistics%2B2010%2Bto%2B2025%2B-%2BPrivate%2BRents%2BOpen%2BData.csv"
)
PUBLICATION_URL = (
    "https://www.gov.scot/publications/private-sector-rent-statistics-scotland-2010-to-2025/"
)
METHODOLOGY_URL = PUBLICATION_URL + "pages/data-and-methodology/"
PUBLICATION = "Private Sector Rent Statistics, Scotland, 2010 to 2025"
PUBLISHED = date(2025, 11, 25)
BRMA = "Lothian"

HEADER = ["BRMA", "Year", "Measure", "Beds", "Value"]
# Source "Beds" label (lower-cased: the file spells it both "Shared" and "shared") -> YAML key.
BEDS = {
    "1 bedroom shared": "shared_1_bedroom",
    "1 bedroom": "bedrooms_1",
    "2 bedroom": "bedrooms_2",
    "3 bedroom": "bedrooms_3",
    "4 bedroom": "bedrooms_4",
}
MEASURES = {
    "Lower Quartile": "lower_quartile_gbp_pcm",
    "Median": "median_gbp_pcm",
    "Mean": "mean_gbp_pcm",
    "Upper Quartile": "upper_quartile_gbp_pcm",
    "Number of Records": "n_records",
}

LICENCE = (
    "Crown copyright, Scottish Government. gov.scot states all content is available under the "
    "Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-"
    "licence/version/3/) except graphic assets and where otherwise stated; no publication-"
    "specific licence statement was found."
)
NOTES = (
    "Scottish Government Private Sector Rent Statistics (publication 'Private Sector Rent "
    "Statistics, Scotland, 2010 to 2025', published 25 November 2025), 'Private Rents Open "
    "Data' CSV, Lothian Broad Rental Market Area rows for the latest year in the file. Monthly "
    "rents in GBP per calendar month; the statistics year runs to the end of September. Source: "
    "Rent Service Scotland's Market Evidence Database; per the methodology page the figures are "
    "based predominantly on advertised rents (tenant turnover or new to market), with the "
    "remainder transactional data from letting agents or landlords, so they describe the "
    "market for new lets, not rents paid by sitting tenants. Excludes social housing, mid-market "
    "rent, halls of residence, tenancies known to involve housing benefit and regulated "
    "tenancies; studios/bedsits and 5+ bedroom properties are not published. Lothian BRMA is "
    "wider than the City of Edinburgh. 'shared_1_bedroom' is the source's '1 Bedroom Shared' "
    "category. Values are rounded to the penny. These are context for a listing's rent, not a "
    "valuation of any property. Parsed by backend/scripts/ingest_rents.py. 'retrieved' "
    "is the date the CSV was downloaded."
)


class IngestError(Exception):
    """The CSV is missing or doesn't contain the expected rows."""


def _number(text: str, *, where: str) -> float:
    try:
        return float(text)
    except ValueError:
        raise IngestError(f"{where}: value {text!r} is not a number") from None


def parse_csv(text: str) -> tuple[int, dict[str, dict[str, float | int]]]:
    """Return ``(latest year, rents by bedroom key)`` for the Lothian BRMA."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    if header != HEADER:
        raise IngestError(f"unexpected header {header!r}, expected {HEADER!r}")
    lothian = [row for row in reader if row and row[0].strip() == BRMA]
    for row in lothian:
        if len(row) != len(HEADER):
            raise IngestError(f"row {row!r} has {len(row)} columns, expected {len(HEADER)}")
    if not lothian:
        raise IngestError(f"no rows for BRMA {BRMA!r}")
    try:
        year = max(int(row[1]) for row in lothian)
    except ValueError as exc:
        raise IngestError(f"non-integer Year in {BRMA} rows: {exc}") from None
    rents: dict[str, dict[str, float | int]] = {key: {} for key in BEDS.values()}
    for _, row_year, measure, beds, value in (r for r in lothian if int(r[1]) == year):
        key = BEDS.get(beds.strip().lower())
        field = MEASURES.get(measure.strip())
        if key is None or field is None:
            raise IngestError(f"unknown category {beds!r} / measure {measure!r}")
        where = f"{BRMA} {row_year} {measure} {beds}"
        if field in rents[key]:
            raise IngestError(f"{where}: duplicate row")
        number = _number(value.strip(), where=where)
        if field == "n_records":
            if not number.is_integer():
                raise IngestError(f"{where}: record count {value!r} is not an integer")
            rents[key][field] = int(number)
        else:
            rents[key][field] = round(number, 2)
    for key, stats in rents.items():
        missing = sorted(set(MEASURES.values()) - set(stats))
        if missing:
            raise IngestError(f"{BRMA} {year} {key}: missing {', '.join(missing)}")
    ordered = {key: {f: stats[f] for f in MEASURES.values()} for key, stats in rents.items()}
    return year, ordered


def read_csv(path: Path) -> str:
    if not path.is_file():
        raise IngestError(f"{path} not found (run with --download)")
    return path.read_text(encoding="utf-8-sig")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download() -> None:
    if RAW_CSV.is_file():
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        response = client.get(SOURCE_URL, timeout=60)
    response.raise_for_status()
    if not response.content.lstrip(b"\xef\xbb\xbf").startswith(",".join(HEADER).encode()):
        raise IngestError(f"{SOURCE_URL} did not return the expected CSV")
    RAW_CSV.write_bytes(response.content)
    print(f"downloaded {SOURCE_URL} -> {RAW_CSV}")


def parse_source() -> dict[str, Any]:
    """The data fields of the YAML (everything except ``meta``) from the raw CSV."""
    try:
        year, rents = parse_csv(read_csv(RAW_CSV))
    except IngestError as exc:
        raise IngestError(f"{RAW_CSV.name}: {exc}") from exc
    return {
        "publisher": "Scottish Government",
        "publication": PUBLICATION,
        "published": PUBLISHED,
        "brma": BRMA,
        "basis": "mostly_advertised_rents",
        "unit": "gbp_per_calendar_month",
        "year": year,
        "period_end": date(year, 9, 30),
        "source_url": SOURCE_URL,
        "source_sha256": sha256(RAW_CSV),
        "methodology_url": METHODOLOGY_URL,
        "rents": rents,
    }


def build_document() -> dict[str, Any]:
    data = parse_source()
    document = {
        "meta": {
            "source_url": SOURCE_URL,
            "retrieved": datetime.fromtimestamp(RAW_CSV.stat().st_mtime).date(),
            "licence": LICENCE,
            "notes": NOTES,
        },
        **data,
    }
    RentReference.model_validate(document)  # fail before writing anything invalid
    return document


def to_yaml(document: dict[str, Any]) -> str:
    header = (
        "# Generated by backend/scripts/ingest_rents.py from the Private Rents Open Data CSV.\n"
        "# Do not edit by hand; re-run the script instead.\n"
    )
    return header + yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def check() -> int:
    try:
        committed = load_reference_file(OUTPUT, RentReference)
    except Exception as exc:
        print(f"invalid {OUTPUT}: {exc}", file=sys.stderr)
        return 1
    if not RAW_CSV.is_file():
        print(f"{OUTPUT.name} is valid (raw CSV not present, not re-parsed)")
        return 0
    if parse_source() != committed.model_dump(mode="python", exclude={"meta"}):
        print(f"{OUTPUT.name} differs from the raw CSV; re-run the script", file=sys.stderr)
        return 1
    print(f"{OUTPUT.name} is valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="fetch the CSV if missing")
    parser.add_argument("--check", action="store_true", help="validate instead of writing")
    args = parser.parse_args(argv)
    try:
        if args.check:
            return check()
        if args.download:
            download()
        document = build_document()
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(to_yaml(document), encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
