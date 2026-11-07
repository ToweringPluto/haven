"""``private_rents``: Private Sector Rent Statistics, Lothian BRMA, every year (rent_stats).

Source: the Scottish Government's "Private Rents Open Data" CSV from "Private Sector Rent
Statistics, Scotland, 2010 to 2025". One row per BRMA x year x measure x bedroom category.
Run ``scripts/inspect_rents_csv.py`` first: it checks the header against
:data:`EXPECTED_HEADER` and lists the categories, so a renamed column fails before loading.

Output:

- ``data/seed/private_rents.json``: one record per (year, bedroom category) with lower
  quartile, median, mean, upper quartile (GBP per calendar month) and record count. The
  benchmark and trend features read this offline.
- ``data/sql/rent_stats.sql``: idempotent SQL creating the ``rent_stats`` TimescaleDB
  hypertable (time column ``period_end``) and upserting the same rows,
  applied to Tiger Cloud by ``scripts/load_db.py``. ``haven.datasets.db.rent_series`` reads
  the database when ``HAVEN_DATABASE_URL`` is set and falls back to the seed otherwise.

The figures are mostly advertised rents at tenant turnover, not rents sitting tenants pay,
and Lothian BRMA covers three council areas (Edinburgh, East Lothian, Midlothian).
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

import httpx

from haven.config import REPO_ROOT
from haven.datasets.loaders.common import OGL_GOV_SCOT, LoaderSourceMissing
from haven.datasets.seeds import SeedDocument, seed_document

DATASET_ID = "private_rents"
BRMA = "Lothian"
EXPECTED_HEADER = ["BRMA", "Year", "Measure", "Beds", "Value"]

RAW_DIR = REPO_ROOT / "data" / "raw" / "rents"
RAW_CSV = RAW_DIR / "private_rents_open_data_2010_2025.csv"
SQL_PATH = REPO_ROOT / "data" / "sql" / "rent_stats.sql"
RETRIEVED_AT = date(2026, 11, 7)
USER_AGENT = "haven-prototype/0.1 (Edinburgh renter-check data layer; one-off download)"

PUBLICATION_URL = (
    "https://www.gov.scot/publications/private-sector-rent-statistics-scotland-2010-to-2025/"
)
SOURCE_URL = (
    "https://www.gov.scot/binaries/content/documents/govscot/publications/statistics/2025/11/"
    "private-sector-rent-statistics-scotland-2010-to-2025/documents/"
    "prs-rent-statistics-2025---private-rents-open-data/"
    "prs-rent-statistics-2025---private-rents-open-data/govscot%3Adocument/"
    "Private%2BSector%2BRent%2BStatistics%2B2010%2Bto%2B2025%2B-%2BPrivate%2BRents%2BOpen%2BData.csv"
)

BEDS = {
    "1 bedroom shared": "1_bed_shared",
    "1 bedroom": "1_bed",
    "2 bedroom": "2_bed",
    "3 bedroom": "3_bed",
    "4 bedroom": "4_bed",
}
MEASURES = {
    "Lower Quartile": "lower_quartile_gbp_pcm",
    "Median": "median_gbp_pcm",
    "Mean": "mean_gbp_pcm",
    "Upper Quartile": "upper_quartile_gbp_pcm",
    "Number of Records": "n_records",
}


class RentsParseError(ValueError):
    """The CSV doesn't have the expected shape."""


def download() -> None:
    """Fetch the CSV once (single request) if it isn't already in ``data/raw/rents/``."""
    if RAW_CSV.is_file():
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        response = client.get(SOURCE_URL, timeout=60)
    response.raise_for_status()
    RAW_CSV.write_bytes(response.content)


def _value(text: str, field: str) -> float | int | None:
    text = text.strip().replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None  # suppressed or blank in the source: kept as null, never defaulted
    if field == "n_records":
        return int(number)
    return round(number, 2)


def parse_series(text: str) -> list[dict[str, Any]]:
    """Lothian records for every year, sorted by (period_end, beds)."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    if header != EXPECTED_HEADER:
        raise RentsParseError(f"unexpected header {header!r}, expected {EXPECTED_HEADER!r}")
    grouped: dict[tuple[int, str], dict[str, Any]] = {}
    for row in reader:
        if not row or row[0].strip() != BRMA:
            continue
        if len(row) != len(EXPECTED_HEADER):
            raise RentsParseError(f"row {row!r} has {len(row)} columns")
        _, year_text, measure, beds, value = row
        beds_key = BEDS.get(beds.strip().lower())
        field = MEASURES.get(measure.strip())
        if beds_key is None or field is None:
            raise RentsParseError(f"unknown category {beds!r} / measure {measure!r}")
        year = int(year_text)
        record = grouped.setdefault(
            (year, beds_key),
            {
                "brma": BRMA,
                "year": year,
                "period_end": date(year, 9, 30).isoformat(),
                "beds": beds_key,
                "is_sample": False,
            },
        )
        if field in record:
            raise RentsParseError(f"duplicate {BRMA} {year} {measure} {beds}")
        record[field] = _value(value, field)
    if not grouped:
        raise RentsParseError(f"no rows for BRMA {BRMA!r}")
    for record in grouped.values():
        for field in MEASURES.values():
            record.setdefault(field, None)
    order = list(BEDS.values())
    return sorted(grouped.values(), key=lambda r: (r["period_end"], order.index(r["beds"])))


def build() -> SeedDocument:
    if not RAW_CSV.is_file():
        raise LoaderSourceMissing(f"{RAW_CSV} not found (scripts/inspect_rents_csv.py --download)")
    records = parse_series(RAW_CSV.read_text(encoding="utf-8-sig"))
    latest = max(r["year"] for r in records)
    return seed_document(
        DATASET_ID,
        source_url=SOURCE_URL,
        as_of=date(latest, 9, 30),
        retrieved_at=RETRIEVED_AT,
        licence_note=OGL_GOV_SCOT,
        records=records,
    )


def _sql_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return repr(value)


SQL_COLUMNS = ["brma", "beds", "period_end", "year", *MEASURES.values(), "is_sample"]


def render_sql(document: SeedDocument) -> str:
    """Idempotent DDL + upserts for the ``rent_stats`` hypertable."""
    lines = [
        "-- Generated by backend/scripts/build_seeds.py from data/seed/private_rents.json.",
        "-- Do not edit by hand. Safe to run repeatedly (IF NOT EXISTS + ON CONFLICT).",
        f"-- Source: {PUBLICATION_URL} (Open Government Licence v3.0).",
        "CREATE EXTENSION IF NOT EXISTS timescaledb;",
        "CREATE TABLE IF NOT EXISTS rent_stats (",
        "    brma text NOT NULL,",
        "    beds text NOT NULL,",
        "    period_end date NOT NULL,",
        "    year integer NOT NULL,",
        "    lower_quartile_gbp_pcm numeric(10, 2),",
        "    median_gbp_pcm numeric(10, 2),",
        "    mean_gbp_pcm numeric(10, 2),",
        "    upper_quartile_gbp_pcm numeric(10, 2),",
        "    n_records integer,",
        "    is_sample boolean NOT NULL DEFAULT false,",
        "    PRIMARY KEY (brma, beds, period_end)",
        ");",
        "SELECT create_hypertable('rent_stats', 'period_end', if_not_exists => TRUE,",
        "                         chunk_time_interval => INTERVAL '5 years');",
        f"INSERT INTO rent_stats ({', '.join(SQL_COLUMNS)}) VALUES",
    ]
    rows = [
        "    (" + ", ".join(_sql_value(r[c]) for c in SQL_COLUMNS) + ")" for r in document.records
    ]
    lines.append(",\n".join(rows))
    updates = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in SQL_COLUMNS if c not in ("brma", "beds", "period_end")
    )
    lines.append(f"ON CONFLICT (brma, beds, period_end) DO UPDATE SET {updates};")
    return "\n".join(lines) + "\n"
