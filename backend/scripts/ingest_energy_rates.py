"""Build ``data/reference/energy_rates.yaml`` from Ofgem's price cap tables.

Ofgem's "Energy price cap unit rates and standing charges" page (``PAGE_URL``) shows, per
region and payment method, the capped unit rate (p/kWh) and daily standing charge (p/day). The
tables are everviz embeds: the page loads ``https://app.everviz.com/inject/<id>/`` scripts whose
``options.data.value`` holds the table rows. This script reads the Direct Debit tables for
single-rate electricity and gas, takes the Southern Scotland row for the current cap period and
writes the YAML reference file with provenance.

As an independent check it also reads Ofgem's "Energy price cap levels" PDF (the licence cap
tables, annual GBP excluding VAT at nil consumption and at typical consumption), derives the unit
rate and standing charge from it and requires them to agree with the published rates after VAT.

Usage (from ``backend/``)::

    uv run python scripts/ingest_energy_rates.py --download  # fetch missing raw files, ingest
    uv run python scripts/ingest_energy_rates.py             # ingest the files in data/raw/
    uv run python scripts/ingest_energy_rates.py --check     # validate the YAML; if the raw
                                                             # files are present, re-parse them

Raw files live in ``data/raw/energy/`` (gitignored). When the cap period changes, update
``PERIOD``, the table URLs (the everviz ids and ``?v=`` versions on the page) and the PDF URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
from haven.reference.energy_rates import FILE_NAME, EnergyRatesReference, FuelRates

RAW_DIR = REPO_ROOT / "data" / "raw" / "energy"
OUTPUT = REFERENCE_DIR / f"{FILE_NAME}.yaml"
PAGE_URL = (
    "https://www.ofgem.gov.uk/information-consumers/energy-advice-households/"
    "get-energy-price-cap-standing-charges-and-unit-rates-region"
)
COPYRIGHT_URL = "https://www.ofgem.gov.uk/copyright"
USER_AGENT = "haven-prototype"
REGION = "Southern Scotland"


@dataclass(frozen=True)
class Period:
    label: str  # as written in Ofgem's column headings
    valid_from: date
    valid_to: date


PERIOD = Period("October to December 2026", date(2026, 10, 1), date(2026, 12, 31))


@dataclass(frozen=True)
class Table:
    fuel: str  # "electricity" | "gas"
    url: str
    filename: str
    title: str  # the everviz table title, checked so a swapped id can't go unnoticed
    vat_rate: float  # VAT included in the published figures, as Ofgem states on PAGE_URL

    @property
    def path(self) -> Path:
        return RAW_DIR / self.filename


TABLES = [
    Table(
        "electricity",
        "https://app.everviz.com/inject/YS_arnkBg/?v=59",
        "everviz_dd.js",
        "Electricity standing charges and unit rates paid by Direct Debit, single rate",
        # "There is no VAT on electricity from 1 October 2026 to 31 March 2027."
        0.0,
    ),
    Table(
        "gas",
        "https://app.everviz.com/inject/NCvaUoTBE/?v=40",
        "everviz_dd_gas.js",
        "Gas standing charges and unit rates paid by Direct Debit",
        # "Figures are rounded to two decimal places and include 5% VAT on gas."
        0.05,
    ),
]


@dataclass(frozen=True)
class CapLevels:
    url: str
    filename: str

    @property
    def path(self) -> Path:
        return RAW_DIR / self.filename


CAP_LEVELS = CapLevels(
    "https://www.ofgem.gov.uk/sites/default/files/2026-08/17a-PDF-Cap-Tables.pdf",
    "17a-PDF-Cap-Tables.pdf",
)
# Typical domestic consumption values the cap levels PDF quotes ("m (2,500kWh)", "(9,500 kWh)").
TDCV_KWH = {"electricity": 2500, "gas": 9500}
DAYS_PER_YEAR = 365
# Published rates are rounded to 2 dp; derived ones carry the PDF's rounding to the penny.
CROSS_CHECK_TOLERANCE = 0.011

LICENCE = (
    f"Crown copyright, Ofgem. Ofgem's copyright page ({COPYRIGHT_URL}) permits re-use of Crown "
    "copyright information (not logos) free of charge under the Open Government Licence (the page "
    "doesn't state a version)."
)
NOTES = (
    f"Ofgem energy price cap for {PERIOD.valid_from} to {PERIOD.valid_to}: capped unit rates "
    f"(p/kWh) and daily standing charges (p/day) for the {REGION} region (SP Energy Networks; "
    "Ofgem's postcode lookup maps EH postcodes here), Direct Debit, default tariff, single-rate "
    "electricity and gas. Parsed from the Direct Debit tables on the source page (everviz embeds, "
    "URLs and sha256 per fuel below) by backend/scripts/ingest_energy_rates.py, and cross-checked "
    f"against Ofgem's cap levels PDF ({CAP_LEVELS.url}). Figures include VAT at vat_rate as "
    "published (5% on gas; Ofgem states no VAT on electricity from 1 October 2026 to 31 March "
    "2027). These are caps on default tariffs, not a renter's actual tariff; fixed or other "
    "tariffs, multi-rate meters and prepayment differ. 'retrieved' is the date the tables were "
    "downloaded."
)

OPTIONS_RE = re.compile(r"var options = (\{.*?\});\s*$", re.MULTILINE)
PENCE_RE = re.compile(r"^(\d+(?:\.\d+)?) pence per (day|kWh)$")
GBP_RE = re.compile(r"(\d{1,3}(?:,\d{3})*\.\d{2})")


class IngestError(Exception):
    """A raw file is missing or doesn't contain the expected table."""


def _norm(text: str) -> str:
    return " ".join(text.split())


def parse_table(text: str, table: Table, period: Period = PERIOD) -> tuple[float, float]:
    """Return ``(standing p/day, unit p/kWh)`` for ``REGION`` from an everviz inject script."""
    match = OPTIONS_RE.search(text)
    if not match:
        raise IngestError("no 'var options = {...};' block found")
    options = json.loads(match.group(1))
    title = re.sub(r"<[^>]+>", " ", options["options"]["title"]["text"])
    if _norm(table.title) not in _norm(title):
        raise IngestError(f"table title {_norm(title)!r} doesn't match {table.title!r}")
    header, *rows = options["data"]["value"]
    header = [_norm(h) for h in header]
    try:
        standing_col = header.index(f"Daily standing charge {period.label}")
        unit_col = header.index(f"Unit rate {period.label}")
    except ValueError as exc:
        raise IngestError(f"no columns for {period.label!r} in {header}") from exc
    matches = [row for row in rows if _norm(row[0]) == REGION]
    if len(matches) != 1:
        raise IngestError(f"expected one {REGION!r} row, found {len(matches)}")
    row = matches[0]
    return _pence(row[standing_col], "day"), _pence(row[unit_col], "kWh")


def _pence(cell: str, unit: str) -> float:
    match = PENCE_RE.match(_norm(cell))
    if not match or match.group(2) != unit:
        raise IngestError(f"cell {cell!r} isn't 'N pence per {unit}'")
    return float(match.group(1))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_fuel(table: Table) -> FuelRates:
    if not table.path.is_file():
        raise IngestError(f"{table.path} not found (run with --download)")
    try:
        standing, unit = parse_table(table.path.read_text(encoding="utf-8"), table)
    except IngestError as exc:
        raise IngestError(f"{table.filename}: {exc}") from exc
    return FuelRates(
        unit_rate_p_per_kwh=unit,
        standing_charge_p_per_day=standing,
        vat_rate=table.vat_rate,
        source_url=table.url,
        source_sha256=sha256(table.path),
    )


# --- cross-check against the cap levels PDF -------------------------------------------------


def parse_cap_levels(pages: list[str]) -> dict[str, tuple[float, float]]:
    """Annual ex-VAT GBP ``(nil kWh, typical kWh)`` for ``REGION`` per fuel, Direct Debit.

    The PDF has one page per fuel and payment method; Direct Debit is "Other Payment Method"
    (page 1 gas, page 4 electricity). Electricity rows wrap, so the amounts can sit on the line
    above the region name. The first two amounts are the single-rate meter columns.
    """
    found: dict[str, tuple[float, float]] = {}
    for page in pages:
        lines = page.splitlines()
        head = " ".join(lines[:15])
        if "Other Payment Method" not in head:
            continue
        fuel = "electricity" if "Electricity" in head else "gas" if "Gas" in head else None
        if fuel is None:
            continue
        for i, line in enumerate(lines):
            if REGION not in line:
                continue
            amounts = GBP_RE.findall(line) or (GBP_RE.findall(lines[i - 1]) if i else [])
            if len(amounts) < 2:
                raise IngestError(f"no amounts next to {REGION!r} on the {fuel} page")
            nil, typical = (float(a.replace(",", "")) for a in amounts[:2])
            found[fuel] = (nil, typical)
    missing = set(TDCV_KWH) - set(found)
    if missing:
        raise IngestError(f"cap levels for {sorted(missing)} not found")
    return found


def derive_rates(
    nil_gbp: float, typical_gbp: float, fuel: str, vat_rate: float
) -> dict[str, float]:
    """Standing charge = nil-consumption level / 365; unit rate = the rest / typical kWh."""
    vat = 1 + vat_rate
    return {
        "standing_charge_p_per_day": nil_gbp * 100 / DAYS_PER_YEAR * vat,
        "unit_rate_p_per_kwh": (typical_gbp - nil_gbp) * 100 / TDCV_KWH[fuel] * vat,
    }


def cross_check(document: EnergyRatesReference, pdf_path: Path) -> list[str]:
    """Differences between the published rates and those derived from the cap levels PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        levels = parse_cap_levels([page.extract_text() or "" for page in pdf.pages])
    problems = []
    for fuel, (nil, typical) in levels.items():
        published: FuelRates = getattr(document, fuel)
        derived = derive_rates(nil, typical, fuel, published.vat_rate)
        for field, b in derived.items():
            a = getattr(published, field)
            if abs(a - b) > CROSS_CHECK_TOLERANCE:
                problems.append(f"{fuel} {field}: published {a} vs cap levels {b:.3f}")
    return problems


# --- build / check --------------------------------------------------------------------------


def download() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for url, path, magic in [(t.url, t.path, b"(function") for t in TABLES] + [
            (CAP_LEVELS.url, CAP_LEVELS.path, b"%PDF")
        ]:
            if path.is_file():
                continue
            response = client.get(url, timeout=60)
            response.raise_for_status()
            if not response.content.lstrip().startswith(magic):
                raise IngestError(f"{url} did not return the expected content")
            path.write_bytes(response.content)
            print(f"downloaded {url} -> {path}")


def retrieved_date() -> date:
    """Date the oldest raw table was downloaded (its modification time)."""
    return min(datetime.fromtimestamp(t.path.stat().st_mtime).date() for t in TABLES)


def build_document() -> dict[str, Any]:
    fuels = {t.fuel: parse_fuel(t) for t in TABLES}
    document = {
        "meta": {
            "source_url": PAGE_URL,
            "retrieved": retrieved_date(),
            "licence": LICENCE,
            "notes": NOTES,
        },
        "region": REGION,
        "payment_method": "direct_debit",
        "tariff": "default_tariff_price_cap",
        "electricity_meter": "single_rate",
        "prices_include_vat": True,
        "valid_from": PERIOD.valid_from,
        "valid_to": PERIOD.valid_to,
        **{fuel: rates.model_dump(mode="python") for fuel, rates in fuels.items()},
    }
    parsed = EnergyRatesReference.model_validate(document)  # fail before writing anything invalid
    if CAP_LEVELS.path.is_file():
        problems = cross_check(parsed, CAP_LEVELS.path)
        if problems:
            raise IngestError("cross-check failed: " + "; ".join(problems))
    return document


def to_yaml(document: dict[str, Any]) -> str:
    header = (
        "# Generated by backend/scripts/ingest_energy_rates.py from Ofgem's price cap tables.\n"
        "# Do not edit by hand; re-run the script instead.\n"
    )
    return header + yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def check() -> int:
    try:
        committed = load_reference_file(OUTPUT, EnergyRatesReference)
    except Exception as exc:
        print(f"invalid {OUTPUT}: {exc}", file=sys.stderr)
        return 1
    if (committed.valid_from, committed.valid_to) != (PERIOD.valid_from, PERIOD.valid_to):
        print(f"{OUTPUT.name}: period doesn't match {PERIOD}; re-run the script")
        return 1
    present = [t for t in TABLES if t.path.is_file()]
    for table in present:
        if parse_fuel(table) != getattr(committed, table.fuel):
            print(f"{OUTPUT.name}: {table.fuel} differs from {table.filename}; re-run the script")
            return 1
    if CAP_LEVELS.path.is_file():
        problems = cross_check(committed, CAP_LEVELS.path)
        if problems:
            print(f"{OUTPUT.name}: cross-check failed: " + "; ".join(problems))
            return 1
    skipped = [t.filename for t in TABLES if t not in present]
    if not CAP_LEVELS.path.is_file():
        skipped.append(CAP_LEVELS.filename)
    note = f" (raw files not present, not re-checked: {', '.join(skipped)})" if skipped else ""
    print(f"{OUTPUT.name} is valid{note}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="fetch missing raw files first")
    parser.add_argument("--check", action="store_true", help="validate instead of writing")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    try:
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
