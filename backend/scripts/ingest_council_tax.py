"""Build ``data/reference/council_tax_edinburgh.yaml`` from the council's charges PDFs.

The City of Edinburgh Council publishes one "Council Tax charges" PDF per financial year. Its
first page has a table with, per band A-H, the annual council tax, Scottish Water water and
sewerage (waste water) charges and their total. This script extracts that table with
pdfplumber, checks that every band is present and that the components add up to the printed
total, and writes the YAML reference file with provenance.

Usage (from ``backend/``)::

    uv run python scripts/ingest_council_tax.py --download  # fetch missing PDFs, then ingest
    uv run python scripts/ingest_council_tax.py             # ingest the PDFs in data/raw/
    uv run python scripts/ingest_council_tax.py --check     # validate the YAML; if the PDFs
                                                            # are present, re-parse and compare

Raw PDFs live in ``data/raw/council_tax/`` (gitignored).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import pdfplumber
import yaml

from haven.config import REFERENCE_DIR, REPO_ROOT
from haven.domain import CouncilTaxBand
from haven.reference import load_reference_file
from haven.reference.council_tax import (
    FILE_NAME,
    BandCharges,
    CouncilTaxReference,
    CouncilTaxYear,
)

RAW_DIR = REPO_ROOT / "data" / "raw" / "council_tax"
OUTPUT = REFERENCE_DIR / f"{FILE_NAME}.yaml"
INDEX_URL = "https://www.edinburgh.gov.uk/counciltaxbands"
TERMS_URL = "https://www.edinburgh.gov.uk/terms"
USER_AGENT = "haven-prototype"


@dataclass(frozen=True)
class Source:
    year: str  # "2025/26"
    url: str
    filename: str

    @property
    def path(self) -> Path:
        return RAW_DIR / self.filename

    @property
    def valid_from(self) -> date:
        # Scottish council tax is charged per financial year, 1 April to 31 March.
        return date(int(self.year[:4]), 4, 1)

    @property
    def valid_to(self) -> date:
        return date(int(self.year[:4]) + 1, 3, 31)


SOURCES = [
    Source(
        "2025/26",
        "https://www.edinburgh.gov.uk/downloads/file/36923/council-tax-charges-2025",
        "council-tax-charges-2025.pdf",
    ),
    Source(
        "2026/27",
        "https://www.edinburgh.gov.uk/downloads/file/39463/council-tax-charges-2026",
        "council-tax-charges-2026.pdf",
    ),
]

LICENCE = (
    "Copyright City of Edinburgh Council, all rights reserved. The council's website terms "
    f"({TERMS_URL}) permit personal, non-commercial use; no open licence is stated. Factual "
    "charge figures reproduced for a non-commercial prototype. Confirm with the council before "
    "redistribution (see docs/DATA_SOURCES.md)."
)
NOTES = (
    "Annual charges per band (A-H) for council tax, water and waste water (sewerage), parsed "
    "with pdfplumber from the council's 'Council Tax charges' PDF for each year (URLs and sha256 "
    "per year below) by backend/scripts/ingest_council_tax.py. Water and waste water are "
    "Scottish Water charges collected with council tax. Full charges before any discount, "
    "exemption or Council Tax Reduction (e.g. single-person discount, student exemption), which "
    "are not modelled. valid_from/valid_to is the financial year, 1 April to 31 March. "
    "'retrieved' is the date the PDFs were downloaded."
)

AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
ROW_RE = re.compile(r"^([A-H])\s")


class IngestError(Exception):
    """A PDF is missing or doesn't contain the expected charges table."""


def _amount(text: str) -> float:
    return float(text.replace(",", ""))


def parse_charges(text: str, year: str) -> dict[CouncilTaxBand, BandCharges]:
    """Extract the per-band charges table from the PDF text of one year.

    Rows of the combined table look like ``A £1,042.34 £185.28 £214.98 £1,442.60``: a band
    letter followed by exactly four amounts. The year-on-year council tax table above it has
    only two amounts per row, so it never matches.
    """
    if f"Council Tax charges {year}" not in text:
        raise IngestError(f"text doesn't mention 'Council Tax charges {year}'")
    bands: dict[CouncilTaxBand, BandCharges] = {}
    for line in text.splitlines():
        line = line.strip()
        row = ROW_RE.match(line)
        amounts = AMOUNT_RE.findall(line)
        if not row or len(amounts) != 4:
            continue
        band = CouncilTaxBand(row.group(1))
        if band in bands:
            raise IngestError(f"band {band} appears twice in the charges table")
        council_tax, water, waste_water, total = (_amount(a) for a in amounts)
        bands[band] = BandCharges(
            council_tax_gbp=council_tax,
            water_gbp=water,
            waste_water_gbp=waste_water,
            total_gbp=total,
        )
    missing = set(CouncilTaxBand) - set(bands)
    if missing:
        raise IngestError(f"bands not found in the charges table: {sorted(missing)}")
    return {b: bands[b] for b in CouncilTaxBand}


def pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_source(source: Source) -> CouncilTaxYear:
    if not source.path.is_file():
        raise IngestError(f"{source.path} not found (run with --download)")
    try:
        bands = parse_charges(pdf_text(source.path), source.year)
    except IngestError as exc:
        raise IngestError(f"{source.filename}: {exc}") from exc
    return CouncilTaxYear(
        source_url=source.url,
        source_sha256=sha256(source.path),
        valid_from=source.valid_from,
        valid_to=source.valid_to,
        bands=bands,
    )


def download(sources: list[Source]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for source in sources:
            if source.path.is_file():
                continue
            response = client.get(source.url, timeout=60)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise IngestError(f"{source.url} did not return a PDF")
            source.path.write_bytes(response.content)
            print(f"downloaded {source.url} -> {source.path}")


def retrieved_date(sources: list[Source]) -> date:
    """Date the oldest raw PDF was downloaded (its modification time)."""
    return min(datetime.fromtimestamp(s.path.stat().st_mtime).date() for s in sources)


def build_document(sources: list[Source]) -> dict[str, Any]:
    years = {s.year: parse_source(s) for s in sources}
    document = {
        "meta": {
            "source_url": INDEX_URL,
            "retrieved": retrieved_date(sources),
            "licence": LICENCE,
            "notes": NOTES,
        },
        "authority": "City of Edinburgh Council",
        "currency": "GBP",
        "period": "annual",
        "years": {key: year.model_dump(mode="python") for key, year in years.items()},
    }
    CouncilTaxReference.model_validate(document)  # fail before writing anything invalid
    return document


def to_yaml(document: dict[str, Any]) -> str:
    def plain(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): plain(v) for k, v in value.items()}
        return value

    header = (
        "# Generated by backend/scripts/ingest_council_tax.py from the council's PDFs.\n"
        "# Do not edit by hand; re-run the script instead.\n"
    )
    body = yaml.safe_dump(plain(document), sort_keys=False, width=100, allow_unicode=True)
    return header + body


def check() -> int:
    try:
        committed = load_reference_file(OUTPUT, CouncilTaxReference)
    except Exception as exc:
        print(f"invalid {OUTPUT}: {exc}", file=sys.stderr)
        return 1
    expected = {s.year for s in SOURCES}
    if set(committed.years) != expected:
        print(f"{OUTPUT.name}: years {sorted(committed.years)} != {sorted(expected)}")
        return 1
    present = [s for s in SOURCES if s.path.is_file()]
    for source in present:
        parsed = parse_source(source)
        if parsed != committed.years[source.year]:
            print(f"{OUTPUT.name}: {source.year} differs from {source.filename}; re-run the script")
            return 1
    skipped = [s.filename for s in SOURCES if s not in present]
    note = f" (raw PDFs not present, not re-parsed: {', '.join(skipped)})" if skipped else ""
    print(f"{OUTPUT.name} is valid{note}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="fetch missing PDFs first")
    parser.add_argument("--check", action="store_true", help="validate instead of writing")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    if args.download:
        download(SOURCES)
    try:
        document = build_document(SOURCES)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(to_yaml(document), encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
