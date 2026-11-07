"""Build ``data/reference/heating_efficiency.yaml`` from SAP 10.2 Tables 4a and 4b.

SAP 10.2 (11-04-2023), published by BRE on behalf of BEIS, lists default seasonal efficiencies
for heating systems whose product data isn't known: Table 4a (all heating systems) and Table 4b
(gas and liquid fuel boilers). This script extracts, with pdfplumber, the rows Haven uses for
the two fuels the cost engine prices (mains gas and electricity), checks that each row sits in
the expected table and heading and is marked "rd" (RdSAP reduced data set), and writes the YAML
reference file with provenance.

Usage (from ``backend/``)::

    uv run python scripts/ingest_heating_efficiency.py --download  # fetch the PDF, ingest
    uv run python scripts/ingest_heating_efficiency.py             # ingest the PDF in data/raw/
    uv run python scripts/ingest_heating_efficiency.py --check     # validate the YAML; if the
                                                                   # PDF is present, re-parse

The raw PDF lives in ``data/raw/heating/`` (gitignored).
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
from haven.domain import MainFuel
from haven.reference import load_reference_file
from haven.reference.heating_efficiency import (
    FILE_NAME,
    FuelEfficiency,
    HeatingEfficiencyReference,
    HeatingSystem,
)

RAW_DIR = REPO_ROOT / "data" / "raw" / "heating"
OUTPUT = REFERENCE_DIR / f"{FILE_NAME}.yaml"
USER_AGENT = "haven-prototype"
SOURCE_URL = "https://files.bregroup.com/SAP/SAP%2010.2%20-%2011-04-2023.pdf"
RAW_PDF = RAW_DIR / "SAP_10.2_11-04-2023.pdf"
DOCUMENT = "SAP 10.2 (11-04-2023)"
VERSION_LINE = "Version 10.2 (11-04-2023)"
# PDF pages read: the title page (version line) and Tables 4a to 4c (printed pages 163-169).
# parse_tables fails if the headings aren't found there, e.g. after a new SAP version.
PAGES = (1, *range(164, 171))

LICENCE = (
    "© Crown copyright 2023. SAP 10.2 is published by BRE on behalf of the Department for "
    "Business, Energy and Industrial Strategy (BEIS; now DESNZ). The document names no specific "
    "licence; Crown copyright information is normally re-usable under the Open Government "
    "Licence v3.0 (UK Government Licensing Framework), but this is not stated on the document "
    "itself. Haven uses only the factual default efficiencies, with attribution."
)
NOTES = (
    "Default seasonal efficiencies (%) of heating systems from SAP 10.2 (11-04-2023), Table 4a "
    "(heating systems) and Table 4b (gas and liquid fuel boilers), used when the actual product "
    "is unknown. The cost engine converts EPC heat demand into fuel bought as heat demand / "
    "efficiency. Listings don't say which system a home has, so the engine treats it as unknown: "
    "a central assumption per fuel plus the range across the listed systems. Only rows marked "
    "'rd' (the RdSAP reduced data set, the method behind EPCs for existing homes) are included; "
    "heat pumps needing evidence of a design flow temperature <= 35°C (SAP 9.3) are excluded. "
    "Space-heating (winter) efficiency is used for both space and water heating because the EPC "
    "heat demand model combines them; Table 4b's summer (water heating) efficiencies are about "
    "10 points lower, so hot water may be slightly underestimated. Table 4c adjustments "
    "(controls, flow temperature) are not applied. These are defaults, not measurements of any "
    "property's system. Parsed by backend/scripts/ingest_heating_efficiency.py. 'retrieved' is "
    "the date the PDF was downloaded."
)
SELECTION = (
    "mains_gas: every gas boiler row of Table 4b marked 'rd' (1998 or later; pre-1998 with "
    "fan-assisted flue; pre-1998 with balanced or open flue), excluding combined primary storage "
    "units and range cooker boilers. electricity: Table 4a electric boilers in heated space, heat "
    "pumps 'in other cases' (no flow temperature evidence), storage heaters, electric underfloor "
    "heating, Electricaire, direct-acting room heaters and electric ceiling heating, all marked "
    "'rd'."
)

GAS_1998 = "Gas boilers (including mains gas, LPG and biogas) 1998 or later"
GAS_FAN = "Gas boilers (including mains gas, LPG and biogas) pre-1998, with fan-assisted flue"
GAS_OPEN = "Gas boilers (including mains gas, LPG and biogas) pre-1998, with balanced or open flue"
GAS_GROUPS = (GAS_1998, GAS_FAN, GAS_OPEN)
CPSU = "Combined Primary Storage Units (CPSU) (mains gas, LPG and biogas)"
TABLE_4B_GROUPS = (*GAS_GROUPS, CPSU, "Liquid fuel boilers", "Range cooker boilers")

TABLE_4A_START = "Table 4a: Heating systems (space and water)"
TABLE_4B_START = "Table 4b: Seasonal efficiency for gas and liquid fuel boilers"
TABLE_4C_START = "Table 4c: Efficiency adjustments"
CATEGORY_RE = re.compile(r"^Category (\d+) : (.+)$")

# <description> <eff> [<eff2>] [<heating type> <responsiveness> | From Table 4d] <code> [rd]
ROW_RE = re.compile(
    r"^(?P<desc>\D.*?) (?P<a>\d{2,3})(?: (?P<b>\d{2,3}))?"
    r"(?: \d (?:\d\.\d+|\d)| From Table 4d)? (?P<code>\d{3})(?P<rd> rd)?$"
)


@dataclass(frozen=True)
class Wanted:
    """A row to extract: its table, SAP code, expected heading and description prefix."""

    table: str
    code: int
    group: str
    description: str


GAS_ROWS = [
    Wanted("4b", 101, GAS_1998, "Regular non-condensing with automatic ignition"),
    Wanted("4b", 102, GAS_1998, "Regular condensing with automatic ignition"),
    Wanted("4b", 103, GAS_1998, "Non-condensing combi with automatic ignition"),
    Wanted("4b", 104, GAS_1998, "Condensing combi with automatic ignition"),
    Wanted("4b", 105, GAS_1998, "Regular non-condensing with permanent pilot light"),
    Wanted("4b", 107, GAS_1998, "Non-condensing combi with permanent pilot light"),
    Wanted("4b", 109, GAS_1998, "Back boiler to radiators"),
    Wanted("4b", 111, GAS_FAN, "Regular, high or unknown thermal capacity"),
    Wanted("4b", 112, GAS_FAN, "Combi"),
    Wanted("4b", 113, GAS_FAN, "Condensing combi"),
    Wanted("4b", 114, GAS_FAN, "Regular, condensing"),
    Wanted("4b", 115, GAS_OPEN, "Regular, wall mounted"),
    Wanted("4b", 116, GAS_OPEN, "Regular, floor mounted, pre 1979"),
    Wanted("4b", 117, GAS_OPEN, "Regular, floor mounted, 1979 to 1997"),
    Wanted("4b", 118, GAS_OPEN, "Combi"),
    Wanted("4b", 119, GAS_OPEN, "Back boiler to radiators"),
]
GAS_CENTRAL_CODES = [102, 104]
GAS_CENTRAL_LABEL = "a condensing gas boiler fitted 1998 or later"
GAS_CENTRAL_BASIS = (
    "A condensing boiler fitted 1998 or later (Table 4b codes 102 regular / 104 combi, 84%), the "
    "highest default for gas boilers. Older or non-condensing boilers have lower defaults, so "
    "the central figure is the low-cost end for the system and the range's high end uses the "
    "lowest listed efficiency."
)

CAT_BOILERS = "Category 2 : BOILER SYSTEMS WITH RADIATORS OR UNDERFLOOR HEATING"
CAT_HEAT_PUMPS = "Category 4 : HEAT PUMPS WITH RADIATORS OR UNDERFLOOR HEATING"
CAT_STORAGE = "Category 7 : ELECTRIC STORAGE SYSTEMS"
CAT_UNDERFLOOR = "Category 8 : ELECTRIC UNDERFLOOR HEATING"
CAT_WARM_AIR = "Category 9 : WARM AIR SYSTEMS (NOT HEAT PUMP)"
CAT_ROOM = "Category 10 : ROOM HEATERS"
CAT_OTHER = "Category 11 : OTHER SPACE HEATING SYSTEMS"

ELECTRIC_ROWS = [
    Wanted("4a", 191, CAT_BOILERS, "Direct acting electric boiler"),
    Wanted("4a", 192, CAT_BOILERS, "Electric CPSU in heated space"),
    Wanted("4a", 193, CAT_BOILERS, "Electric dry core storage boiler in heated space"),
    Wanted("4a", 195, CAT_BOILERS, "Electric water storage boiler in heated space"),
    Wanted("4a", 221, CAT_HEAT_PUMPS, "Ground source heat pump in other cases"),
    Wanted("4a", 223, CAT_HEAT_PUMPS, "Water source heat pump, in other cases"),
    Wanted("4a", 224, CAT_HEAT_PUMPS, "Air source heat pump in other cases"),
    Wanted("4a", 401, CAT_STORAGE, "Old (large volume) storage heaters"),
    Wanted("4a", 402, CAT_STORAGE, "Slimline storage heaters"),
    Wanted("4a", 404, CAT_STORAGE, "Fan storage heaters"),
    Wanted("4a", 408, CAT_STORAGE, "Integrated storage+direct-acting heater"),
    Wanted("4a", 409, CAT_STORAGE, "High heat retention storage heaters"),
    Wanted("4a", 421, CAT_UNDERFLOOR, "In concrete slab (off-peak only)"),
    Wanted("4a", 422, CAT_UNDERFLOOR, "Integrated (storage+direct-acting)"),
    Wanted("4a", 424, CAT_UNDERFLOOR, "In screed above insulation"),
    Wanted("4a", 515, CAT_WARM_AIR, "Electricaire system"),
    Wanted("4a", 691, CAT_ROOM, "Panel, convector or radiant heaters"),
    Wanted("4a", 693, CAT_ROOM, "Portable electric heaters"),
    Wanted("4a", 694, CAT_ROOM, "Water- or oil-filled radiators"),
    Wanted("4a", 701, CAT_OTHER, "Electric ceiling heating"),
]
ELECTRIC_CENTRAL_CODES = [401, 402, 404, 408, 409, 691, 693, 694]
ELECTRIC_CENTRAL_LABEL = "storage heaters or direct-acting electric heaters"
ELECTRIC_CENTRAL_BASIS = (
    "Storage heaters or direct-acting electric heaters (Table 4a, 100%: all the electricity "
    "becomes heat in the home). A heat pump would buy less electricity (SAP default 170% where "
    "there is no product data or flow temperature evidence), which sets the range's low end."
)


class IngestError(Exception):
    """The PDF is missing or doesn't contain the expected tables or rows."""


@dataclass(frozen=True)
class Row:
    table: str
    group: str
    description: str
    a: int
    b: int | None
    code: int
    rdsap: bool


def _section(lines: list[str], start: str, end: str) -> list[str]:
    starts = [i for i, line in enumerate(lines) if line == start]
    if len(starts) != 1:
        raise IngestError(f"expected one '{start}' heading, found {len(starts)}")
    ends = [i for i, line in enumerate(lines) if line == end and i > starts[0]]
    if not ends:
        raise IngestError(f"'{end}' heading not found after '{start}'")
    return lines[starts[0] + 1 : ends[0]]


def _rows(lines: list[str], table: str, groups: tuple[str, ...] | None) -> dict[int, Row]:
    """Parse table rows, tagging each with the heading (Table 4b group / 4a category) above it."""
    rows: dict[int, Row] = {}
    group = ""
    for line in lines:
        if groups is None:
            category = CATEGORY_RE.match(line)
            if category:
                group = line
                continue
        elif line in groups:
            group = line
            continue
        row = ROW_RE.match(line)
        if not row:
            continue
        code = int(row["code"])
        parsed = Row(
            table=table,
            group=group,
            description=row["desc"].strip(),
            a=int(row["a"]),
            b=None if row["b"] is None else int(row["b"]),
            code=code,
            rdsap=row["rd"] is not None,
        )
        previous = rows.get(code)
        if previous is not None and (previous.a, previous.b) != (parsed.a, parsed.b):
            raise IngestError(f"Table {table} code {code} appears with different efficiencies")
        rows.setdefault(code, parsed)
    return rows


def parse_tables(text: str) -> tuple[dict[int, Row], dict[int, Row]]:
    """Rows of Table 4a and Table 4b, keyed by SAP code."""
    if VERSION_LINE not in text:
        raise IngestError(f"document version {VERSION_LINE!r} not found")
    lines = [line.strip() for line in text.splitlines()]
    table_4a = _rows(_section(lines, TABLE_4A_START, TABLE_4B_START), "4a", None)
    table_4b = _rows(_section(lines, TABLE_4B_START, TABLE_4C_START), "4b", TABLE_4B_GROUPS)
    return table_4a, table_4b


def _system(row: Row | None, wanted: Wanted) -> HeatingSystem:
    where = f"Table {wanted.table} code {wanted.code}"
    if row is None:
        raise IngestError(f"{where} not found")
    if row.group != wanted.group:
        raise IngestError(f"{where} is under {row.group!r}, expected {wanted.group!r}")
    if not row.description.startswith(wanted.description):
        raise IngestError(f"{where} reads {row.description!r}, expected {wanted.description!r}")
    if not row.rdsap:
        raise IngestError(f"{where} is not marked 'rd'")
    return HeatingSystem(
        table="4b" if wanted.table == "4b" else "4a",
        code=wanted.code,
        group=wanted.group,
        description=row.description,
        space_efficiency_pct=row.a,
        water_efficiency_pct=row.b,
        rdsap=True,
    )


def build_fuels(text: str) -> dict[MainFuel, FuelEfficiency]:
    table_4a, table_4b = parse_tables(text)

    def fuel(rows: list[Wanted], central: list[int], label: str, basis: str) -> FuelEfficiency:
        systems = [
            _system((table_4b if w.table == "4b" else table_4a).get(w.code), w) for w in rows
        ]
        central_pct = {s.space_efficiency_pct for s in systems if s.code in central}
        if len(central_pct) != 1:
            raise IngestError(f"central codes {central} don't share one efficiency")
        return FuelEfficiency(
            central_pct=central_pct.pop(),
            central_codes=central,
            central_label=label,
            central_basis=basis,
            systems=systems,
        )

    return {
        MainFuel.mains_gas: fuel(GAS_ROWS, GAS_CENTRAL_CODES, GAS_CENTRAL_LABEL, GAS_CENTRAL_BASIS),
        MainFuel.electricity: fuel(
            ELECTRIC_ROWS, ELECTRIC_CENTRAL_CODES, ELECTRIC_CENTRAL_LABEL, ELECTRIC_CENTRAL_BASIS
        ),
    }


def pdf_text(path: Path, pages: tuple[int, ...] = PAGES) -> str:
    """Text of the given 1-based pages (the whole PDF is ~200 pages and slow to extract)."""
    if not path.is_file():
        raise IngestError(f"{path} not found (run with --download)")
    with pdfplumber.open(path) as pdf:
        if max(pages) > len(pdf.pages):
            raise IngestError(f"{path.name} has {len(pdf.pages)} pages, expected {max(pages)}+")
        return "\n".join(pdf.pages[n - 1].extract_text() or "" for n in pages)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download() -> None:
    if RAW_PDF.is_file():
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        response = client.get(SOURCE_URL, timeout=120)
        response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise IngestError(f"{SOURCE_URL} did not return a PDF")
    RAW_PDF.write_bytes(response.content)
    print(f"downloaded {SOURCE_URL} -> {RAW_PDF}")


def retrieved_date() -> date:
    """Date the raw PDF was downloaded (its modification time)."""
    return datetime.fromtimestamp(RAW_PDF.stat().st_mtime).date()


def parse_sources() -> dict[str, Any]:
    """The data fields of the YAML (everything except ``meta``) from the raw PDF."""
    try:
        fuels = build_fuels(pdf_text(RAW_PDF))
    except IngestError as exc:
        raise IngestError(f"{RAW_PDF.name}: {exc}") from exc
    return {
        "publisher": "BRE on behalf of BEIS",
        "document": DOCUMENT,
        "source_url": SOURCE_URL,
        "source_sha256": sha256(RAW_PDF),
        "selection": SELECTION,
        "fuels": {
            key.value: value.model_dump(mode="python", exclude_defaults=False)
            for key, value in fuels.items()
        },
    }


def build_document() -> dict[str, Any]:
    document = {
        "meta": {
            "source_url": SOURCE_URL,
            "retrieved": retrieved_date(),
            "licence": LICENCE,
            "notes": NOTES,
        },
        **parse_sources(),
    }
    HeatingEfficiencyReference.model_validate(document)  # fail before writing anything invalid
    return document


def to_yaml(document: dict[str, Any]) -> str:
    header = (
        "# Generated by backend/scripts/ingest_heating_efficiency.py from SAP 10.2 Tables 4a/4b.\n"
        "# Do not edit by hand; re-run the script instead.\n"
    )
    return header + yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def check() -> int:
    try:
        committed = load_reference_file(OUTPUT, HeatingEfficiencyReference)
    except Exception as exc:
        print(f"invalid {OUTPUT}: {exc}", file=sys.stderr)
        return 1
    if not RAW_PDF.is_file():
        print(f"{OUTPUT.name} is valid (raw PDF not present, not re-parsed: {RAW_PDF.name})")
        return 0
    data = committed.model_dump(mode="json", exclude={"meta"})
    try:
        parsed = HeatingEfficiencyReference.model_validate(
            {"meta": committed.meta.model_dump(), **parse_sources()}
        ).model_dump(mode="json", exclude={"meta"})
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if parsed != data:
        print(f"{OUTPUT.name} differs from the raw PDF; re-run the script", file=sys.stderr)
        return 1
    print(f"{OUTPUT.name} is valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="fetch the PDF first")
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
