"""Build ``data/reference/electricity_lighting_appliances.yaml`` from Ofgem's TDCV decision.

Ofgem's "Review of typical domestic consumption values: decision" (27 May 2026) sets the
Typical Domestic Consumption Values used from 1 July 2026. Its Table 1 lists, per meter type,
the 2023 and 2026 TDCV for the low, medium and high usage levels. This script extracts the
**Electricity, Profile Class 1 (standard single-rate meters)** rows with pdfplumber, checks that
each row's "Change" column equals 2026 minus 2023, and writes the YAML reference file with
provenance. The March 2026 consultation is checked for the sentence stating the method (lower
quartile, median and upper quartile of household consumption), so the low/high meaning recorded
in the YAML is the publisher's own.

Usage (from ``backend/``)::

    uv run python scripts/ingest_electricity_tdcv.py --download  # fetch missing PDFs, ingest
    uv run python scripts/ingest_electricity_tdcv.py             # ingest the PDFs in data/raw/
    uv run python scripts/ingest_electricity_tdcv.py --check     # validate the YAML; if the
                                                                 # PDFs are present, re-parse

Raw PDFs live in ``data/raw/electricity/`` (gitignored).
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
from haven.reference import load_reference_file
from haven.reference.electricity_use import FILE_NAME, ElectricityUseReference, UsageLevels

RAW_DIR = REPO_ROOT / "data" / "raw" / "electricity"
OUTPUT = REFERENCE_DIR / f"{FILE_NAME}.yaml"
USER_AGENT = "haven-prototype"


@dataclass(frozen=True)
class Source:
    url: str
    filename: str

    @property
    def path(self) -> Path:
        return RAW_DIR / self.filename


DECISION = Source(
    "https://www.ofgem.gov.uk/sites/default/files/2026-05/"
    "Review%20of%20typical%20domestic%20consumption%20values%20decision.pdf",
    "TDCV_2026_decision.pdf",
)
CONSULTATION = Source(
    "https://www.ofgem.gov.uk/sites/default/files/2026-03/"
    "Review%20of%20typical%20domestic%20consumption%20values%20consultation.pdf",
    "TDCV_2026_consultation.pdf",
)
SOURCES = [DECISION, CONSULTATION]

# Dates as printed in the decision ("Publication date: 27 May 2026", "Stage 4 Implementation
# of new TDCV values: 1 July 2026"). parse_decision checks the text still says so.
DECISION_PUBLISHED = date(2026, 5, 27)
VALID_FROM = date(2026, 7, 1)
LEVELS = ("Low", "Medium", "High")

LICENCE = (
    "Crown copyright 2026, Ofgem. The decision document states its text may be reproduced "
    "(excluding logos) under the Open Government Licence, acknowledged as Crown copyright with "
    "the document title 'Review of typical domestic consumption values: decision'."
)
NOTES = (
    "Ofgem Typical Domestic Consumption Values (TDCVs) for electricity, Profile Class 1 "
    "(standard single-rate meters), annual kWh, Great Britain, in use from 1 July 2026 (Table 1 "
    "of the decision, published 27 May 2026). Per Ofgem's March 2026 consultation (paragraph "
    "2.9, method_source_url), low/medium/high are the lower quartile, median and upper quartile "
    "of household consumption over the two most recent years of DESNZ meter-level data. These "
    "are ALL metered electricity on single-rate meters, not a lighting/appliance measurement: "
    "they include electric cooking and any electric heating in those homes, and the EPC heat "
    "demand model (energy_kwh_per_m2_edinburgh.yaml) excludes lighting and appliances. For a "
    "gas-heated home they are the closest official proxy for non-heating electricity; for an "
    "electrically heated home, adding them to heat demand may double-count some heating. They "
    "are GB-wide and independent of floor area and occupants; the quartiles describe spread "
    "between households, not uncertainty for one property. Parsed by "
    "backend/scripts/ingest_electricity_tdcv.py. 'retrieved' is the date the PDFs were "
    "downloaded."
)

TABLE_HEADER = "Profile Class 1 (Standard single-rate meters, kWh per year)"
COLUMNS_RE = re.compile(r"^Usage Level 2023 TDCV 2026 TDCV Change$")
_KWH = r"(\d{1,2},\d{3}|\d{3})"
ROW_RE = re.compile(rf"^(Low|Medium|High) {_KWH} {_KWH} ([-+]?[\d,]+)$")
METHOD_SENTENCE = "calculating the lower, median and upper quartile of household consumption"


class IngestError(Exception):
    """A PDF is missing or doesn't contain the expected table or text."""


def _kwh(text: str) -> int:
    return int(text.replace(",", "").replace("+", ""))


def _flat(text: str) -> str:
    return " ".join(text.split())


def parse_decision(text: str) -> UsageLevels:
    """Extract the 2026 single-rate electricity TDCVs from the decision's text.

    Table 1 reads (one meter type per block)::

        Electricity - Profile Class 1 (Standard single-rate meters, kWh per year)
        Usage Level 2023 TDCV 2026 TDCV Change
        Low 1,800 1,600 -200
        ...
    """
    flat = _flat(text)
    if f"Publication date: {DECISION_PUBLISHED.day} May {DECISION_PUBLISHED.year}" not in flat:
        raise IngestError("decision publication date not found (expected 27 May 2026)")
    if "Implementation of new TDCV values: 1 July 2026" not in flat:
        raise IngestError("implementation date 1 July 2026 not found")
    lines = [line.strip() for line in text.splitlines()]
    starts = [i for i, line in enumerate(lines) if line.endswith(TABLE_HEADER)]
    if len(starts) != 1:
        raise IngestError(f"expected one '{TABLE_HEADER}' table header, found {len(starts)}")
    start = starts[0]
    if not COLUMNS_RE.match(lines[start + 1] if start + 1 < len(lines) else ""):
        raise IngestError("column header 'Usage Level 2023 TDCV 2026 TDCV Change' not found")
    values: dict[str, int] = {}
    for line in lines[start + 2 : start + 2 + len(LEVELS)]:
        row = ROW_RE.match(line)
        if not row:
            raise IngestError(f"unexpected row in the single-rate table: {line!r}")
        level, old, new, change = row.group(1), *(_kwh(g) for g in row.groups()[1:])
        if new - old != change:
            raise IngestError(f"{level}: change {change} != {new} - {old}")
        values[level] = new
    if tuple(values) != LEVELS:
        raise IngestError(f"expected rows {LEVELS}, found {tuple(values)}")
    return UsageLevels(
        low_kwh_per_year=values["Low"],
        medium_kwh_per_year=values["Medium"],
        high_kwh_per_year=values["High"],
    )


def check_method(text: str) -> None:
    """The consultation must state the quartile method the YAML relies on."""
    if METHOD_SENTENCE not in _flat(text):
        raise IngestError(f"method sentence not found: {METHOD_SENTENCE!r}")


def pdf_text(path: Path) -> str:
    if not path.is_file():
        raise IngestError(f"{path} not found (run with --download)")
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def parse_sources() -> dict[str, Any]:
    """The data fields of the YAML (everything except ``meta``) from the raw PDFs."""
    try:
        levels = parse_decision(pdf_text(DECISION.path))
    except IngestError as exc:
        raise IngestError(f"{DECISION.filename}: {exc}") from exc
    try:
        check_method(pdf_text(CONSULTATION.path))
    except IngestError as exc:
        raise IngestError(f"{CONSULTATION.filename}: {exc}") from exc
    return {
        "publisher": "Ofgem",
        "measure": "typical_domestic_consumption_values",
        "geography": "Great Britain",
        "meter": "profile_class_1_single_rate",
        "end_uses": "all_metered_electricity",
        "statistic": "lower_quartile_median_upper_quartile",
        "lighting_and_appliances_only": False,
        "decision_published": DECISION_PUBLISHED,
        "valid_from": VALID_FROM,
        "source_url": DECISION.url,
        "source_sha256": sha256(DECISION.path),
        "method_source_url": CONSULTATION.url,
        "electricity": levels.model_dump(mode="python"),
    }


def build_document() -> dict[str, Any]:
    document = {
        "meta": {
            "source_url": DECISION.url,
            "retrieved": retrieved_date(SOURCES),
            "licence": LICENCE,
            "notes": NOTES,
        },
        **parse_sources(),
    }
    ElectricityUseReference.model_validate(document)  # fail before writing anything invalid
    return document


def to_yaml(document: dict[str, Any]) -> str:
    header = (
        "# Generated by backend/scripts/ingest_electricity_tdcv.py from Ofgem's TDCV decision.\n"
        "# Do not edit by hand; re-run the script instead.\n"
    )
    return header + yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def check() -> int:
    try:
        committed = load_reference_file(OUTPUT, ElectricityUseReference)
    except Exception as exc:
        print(f"invalid {OUTPUT}: {exc}", file=sys.stderr)
        return 1
    missing = [s.filename for s in SOURCES if not s.path.is_file()]
    if missing:
        print(f"{OUTPUT.name} is valid (raw PDFs not present, not re-parsed: {', '.join(missing)})")
        return 0
    data = committed.model_dump(mode="python", exclude={"meta"})
    if parse_sources() != data:
        print(f"{OUTPUT.name} differs from the raw PDFs; re-run the script", file=sys.stderr)
        return 1
    print(f"{OUTPUT.name} is valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="fetch missing PDFs first")
    parser.add_argument("--check", action="store_true", help="validate instead of writing")
    args = parser.parse_args(argv)
    try:
        if args.check:
            return check()
        if args.download:
            download(SOURCES)
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
