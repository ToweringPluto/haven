"""Build ``data/reference/energy_kwh_per_m2_edinburgh.yaml`` from the Scottish EPC register.

Streams every quarterly CSV extracted by ``scripts/fetch_epc.py`` (``data/raw/epc/extracted/``),
keeps City of Edinburgh certificates (``LOCAL_AUTHORITY_LABEL == "Edinburgh City"``), keeps the
latest certificate per ``BUILDING_REFERENCE_NUMBER``, and computes, per EPC band × property type
× main heating fuel, the median and interquartile range of

    (SPACE_HEATING_DEMAND + WATER_HEATING_DEMAND) / TOTAL_FLOOR_AREA   [kWh/m²/year]

with counts. Groups with fewer than ``MIN_GROUP_N`` certificates are dropped; their certificates
still count towards the EPC-band-only fallback groups. Column names come from the data
dictionary shipped with the dataset (the "EPD Publication Note" PDF in the archive). That
dictionary has no lighting kWh column, so lighting is **not** included (the YAML says so).

Each CSV has two header rows: column codes, then human labels (skipped). Files are UTF-8 with a
BOM; a few label cells hold U+FFFD, so decoding uses ``errors="replace"``. Address columns are
never read.

Usage (from ``backend/``)::

    uv run python scripts/ingest_epc.py           # read the CSVs (a few minutes), write the YAML
    uv run python scripts/ingest_epc.py --check   # validate the committed YAML (no CSVs needed)
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from haven.config import REFERENCE_DIR
from haven.domain import EpcBand, MainFuel, PropertyType
from haven.reference import load_reference_file
from haven.reference.energy_model import FILE_NAME, MIN_GROUP_N, EnergyModelReference

try:
    from scripts import fetch_epc
except ModuleNotFoundError:  # run as `python scripts/ingest_epc.py`: scripts/ is sys.path[0]
    import fetch_epc  # type: ignore[no-redef]

ARCHIVE = fetch_epc.ARCHIVE
DATASET_URL = fetch_epc.DATASET_URL
EXPECTED_SHA256 = fetch_epc.EXPECTED_SHA256
EXTRACT_DIR = fetch_epc.EXTRACT_DIR
OUTPUT = REFERENCE_DIR / f"{FILE_NAME}.yaml"
LOCAL_AUTHORITY = "Edinburgh City"
DATASET_RELEASE = "Q4 2016 to Q3 2026 (extracted 21 October 2026)"
# Floor-area limits the publisher already applies (publication note, "Quality assurance").
MIN_FLOOR_AREA_M2 = 15.0
MAX_FLOOR_AREA_M2 = 1500.0

COLUMNS = (
    "BUILDING_REFERENCE_NUMBER",
    "LODGEMENT_DATE",
    "CREATED_AT",
    "LOCAL_AUTHORITY_LABEL",
    "CURRENT_ENERGY_RATING",
    "PROPERTY_TYPE",
    "MAIN_FUEL",
    "MAINHEAT_DESCRIPTION",
    "TOTAL_FLOOR_AREA",
    "SPACE_HEATING_DEMAND",
    "WATER_HEATING_DEMAND",
)
NUMERATOR_COLUMNS = ["SPACE_HEATING_DEMAND", "WATER_HEATING_DEMAND"]

PROPERTY_TYPES = {
    "flat": PropertyType.flat,
    "maisonette": PropertyType.maisonette,
    "house": PropertyType.house,
    "bungalow": PropertyType.bungalow,
    "park home": PropertyType.other,
}

LICENCE = (
    "Open Government Licence v3.0 for all non-address fields, per the publisher's note shipped "
    "with the dataset. Address fields (ADDRESS1, ADDRESS2, POST_TOWN, POSTCODE; Royal Mail "
    "copyright) are not read or stored."
)
NOTES = (
    "Calculated annual heat demand per m2 of floor area for City of Edinburgh dwellings: "
    "(SPACE_HEATING_DEMAND + WATER_HEATING_DEMAND) / TOTAL_FLOOR_AREA, from the Scottish "
    "Government domestic EPC register extract (all quarterly CSVs in the release, latest "
    "certificate per BUILDING_REFERENCE_NUMBER), computed by backend/scripts/ingest_epc.py. "
    "These are SAP/RdSAP modelled demands under standardised occupancy, not metered use, and "
    "heat demand rather than fuel delivered (heating-system efficiency is not applied). Lighting "
    "is NOT included: the data dictionary has no lighting kWh column (only LIGHTING_COST_CURRENT "
    "in GBP). Groups are EPC band (CURRENT_ENERGY_RATING) x PROPERTY_TYPE x main heating fuel "
    "(MAIN_FUEL; when blank, as in most 2025-26 certificates, the first MAINHEAT_DESCRIPTION "
    "entry), dropped when n < min_group_n; band_groups are the fallback. Community heating and "
    "fuels other than mains gas or electricity are 'other'. Quartiles use Python's "
    "statistics.quantiles(method='inclusive'), rounded to 0.1 kWh/m2. The EPC register is not "
    "the whole housing stock (EPCs are only needed on sale, rental or construction). 'retrieved' "
    "is the date the archive was downloaded."
)


@dataclass(frozen=True)
class Record:
    building_ref: str
    lodged: str  # ISO date string, compared lexically
    created: str
    epc_band: EpcBand
    property_type: PropertyType | None
    main_fuel: MainFuel | None
    kwh_per_m2: float


def iter_rows(paths: Iterable[Path]) -> Iterator[dict[str, str]]:
    """Yield the needed columns of every data row (the human-label row 2 is skipped)."""
    for path in paths:
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
            reader = csv.reader(fh)
            header = [h.strip() for h in next(reader)]
            next(reader, None)  # row 2: human-readable labels
            missing = [c for c in COLUMNS if c not in header]
            if missing:
                raise SystemExit(f"{path.name}: missing column(s) {missing}")
            idx = {c: header.index(c) for c in COLUMNS}
            for row in reader:
                if len(row) < len(header):
                    continue
                yield {c: row[i] for c, i in idx.items()}


def map_property_type(raw: str) -> PropertyType | None:
    return PROPERTY_TYPES.get(raw.strip().lower())


def map_main_fuel(main_fuel: str, mainheat_description: str) -> MainFuel | None:
    """Main heating fuel from MAIN_FUEL, or from the first heating system description if blank.

    Returns ``None`` (unknown) when neither field says what the fuel is.
    """
    text = main_fuel.strip().lower()
    if not text:
        text = mainheat_description.split("|")[0].strip().lower()
    if not text or text.startswith("no heating/hot-water system or data is from a community"):
        return None
    # "mains gas (not community)" is an individual system; "(community)" / "Community scheme"
    # is a heat network, whose cost isn't a domestic gas/electricity tariff.
    if "community" in text.replace("not community", ""):
        return MainFuel.other
    if "mains gas" in text:
        return MainFuel.mains_gas
    if "electric" in text:
        return MainFuel.electricity
    return MainFuel.other


def _number(raw: str) -> float | None:
    try:
        return float(raw.strip())
    except ValueError:
        return None


def parse_record(row: dict[str, str]) -> Record | str:
    """A usable record, or the reason the row is excluded."""
    try:
        band = EpcBand(row["CURRENT_ENERGY_RATING"].strip().upper())
    except ValueError:
        return "invalid_epc_band"
    area = _number(row["TOTAL_FLOOR_AREA"])
    if area is None or not MIN_FLOOR_AREA_M2 <= area <= MAX_FLOOR_AREA_M2:
        return "invalid_floor_area"
    space = _number(row["SPACE_HEATING_DEMAND"])
    water = _number(row["WATER_HEATING_DEMAND"])
    if space is None or water is None or space < 0 or water < 0:
        return "invalid_heat_demand"
    return Record(
        building_ref=row["BUILDING_REFERENCE_NUMBER"].strip(),
        lodged=row["LODGEMENT_DATE"].strip(),
        created=row["CREATED_AT"].strip(),
        epc_band=band,
        property_type=map_property_type(row["PROPERTY_TYPE"]),
        main_fuel=map_main_fuel(row["MAIN_FUEL"], row["MAINHEAT_DESCRIPTION"]),
        kwh_per_m2=(space + water) / area,
    )


@dataclass
class Collected:
    records: list[Record]
    read: int
    duplicates_removed: int
    excluded: Counter[str]


def collect(rows: Iterable[dict[str, str]]) -> Collected:
    """Filter to Edinburgh, parse, and keep the latest certificate per building."""
    latest: dict[str, Record] = {}
    anonymous: list[Record] = []
    excluded: Counter[str] = Counter()
    read = 0
    duplicates = 0
    for row in rows:
        if row["LOCAL_AUTHORITY_LABEL"].strip() != LOCAL_AUTHORITY:
            continue
        read += 1
        parsed = parse_record(row)
        if isinstance(parsed, str):
            excluded[parsed] += 1
            continue
        if not parsed.building_ref:
            anonymous.append(parsed)
            continue
        current = latest.get(parsed.building_ref)
        if current is None:
            latest[parsed.building_ref] = parsed
            continue
        duplicates += 1
        if (parsed.lodged, parsed.created) > (current.lodged, current.created):
            latest[parsed.building_ref] = parsed
    return Collected([*latest.values(), *anonymous], read, duplicates, excluded)


def distribution(values: list[float]) -> dict[str, Any]:
    if len(values) == 1:
        q1 = med = q3 = values[0]
    else:
        q1, med, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return {"n": len(values), "median": round(med, 1), "q1": round(q1, 1), "q3": round(q3, 1)}


def aggregate(
    records: Iterable[Record], min_n: int = MIN_GROUP_N
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Band-level and (band, type, fuel) distributions, each kept only when n >= ``min_n``."""
    by_band: dict[EpcBand, list[float]] = defaultdict(list)
    by_group: dict[tuple[EpcBand, PropertyType, MainFuel], list[float]] = defaultdict(list)
    for r in records:
        by_band[r.epc_band].append(r.kwh_per_m2)
        if r.property_type is not None and r.main_fuel is not None:
            by_group[(r.epc_band, r.property_type, r.main_fuel)].append(r.kwh_per_m2)

    band_order = list(EpcBand)
    type_order = list(PropertyType)
    fuel_order = list(MainFuel)
    bands = [
        {"epc_band": band.value, **distribution(sorted(values))}
        for band, values in sorted(by_band.items(), key=lambda kv: band_order.index(kv[0]))
        if len(values) >= min_n
    ]
    groups = [
        {
            "epc_band": band.value,
            "property_type": ptype.value,
            "main_fuel": fuel.value,
            **distribution(sorted(values)),
        }
        for (band, ptype, fuel), values in sorted(
            by_group.items(),
            key=lambda kv: (
                band_order.index(kv[0][0]),
                type_order.index(kv[0][1]),
                fuel_order.index(kv[0][2]),
            ),
        )
        if len(values) >= min_n
    ]
    return bands, groups


def build_document(
    rows: Iterable[dict[str, str]],
    *,
    retrieved: date,
    archive_sha256: str,
    min_n: int = MIN_GROUP_N,
) -> dict[str, Any]:
    collected = collect(rows)
    bands, groups = aggregate(collected.records, min_n)
    document: dict[str, Any] = {
        "meta": {
            "source_url": DATASET_URL,
            "retrieved": retrieved,
            "licence": LICENCE,
            "notes": NOTES,
        },
        "local_authority": LOCAL_AUTHORITY,
        "dataset_release": DATASET_RELEASE,
        "archive_sha256": archive_sha256,
        "metric": "space_and_water_heating_demand_kwh_per_m2_year",
        "numerator_columns": NUMERATOR_COLUMNS,
        "denominator_column": "TOTAL_FLOOR_AREA",
        "lighting_included": False,
        "min_group_n": min_n,
        "quantile_method": "inclusive",
        "records": {
            "read": collected.read,
            "duplicates_removed": collected.duplicates_removed,
            "excluded": dict(sorted(collected.excluded.items())),
            "used": len(collected.records),
            "without_property_type": sum(r.property_type is None for r in collected.records),
            "without_main_fuel": sum(r.main_fuel is None for r in collected.records),
        },
        "band_groups": bands,
        "groups": groups,
    }
    EnergyModelReference.model_validate(document)  # fail before writing anything invalid
    return document


def to_yaml(document: dict[str, Any]) -> str:
    header = (
        "# Generated by backend/scripts/ingest_epc.py from the Scottish EPC register extract.\n"
        "# Do not edit by hand; re-run the script instead.\n"
    )
    body = yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)
    return header + body


def check() -> int:
    try:
        committed = load_reference_file(OUTPUT, EnergyModelReference)
    except Exception as exc:
        print(f"invalid {OUTPUT}: {exc}", file=sys.stderr)
        return 1
    problems = []
    if committed.archive_sha256 != EXPECTED_SHA256:
        problems.append(
            f"archive_sha256 {committed.archive_sha256} != fetch_epc.EXPECTED_SHA256; re-run"
        )
    if committed.min_group_n != MIN_GROUP_N:
        problems.append(f"min_group_n {committed.min_group_n} != {MIN_GROUP_N}")
    if not committed.band_groups:
        problems.append("no band_groups")
    if problems:
        for p in problems:
            print(f"{OUTPUT.name}: {p}", file=sys.stderr)
        return 1
    print(
        f"{OUTPUT.name} is valid: {len(committed.band_groups)} band groups, "
        f"{len(committed.groups)} band x type x fuel groups, {committed.records.used} certificates"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="validate the committed YAML")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    csvs = sorted(EXTRACT_DIR.glob("*.csv"))
    if not csvs or not ARCHIVE.is_file():
        print(f"no EPC CSVs under {EXTRACT_DIR}; run scripts/fetch_epc.py", file=sys.stderr)
        return 1
    digest = fetch_epc.sha256(ARCHIVE)
    if digest != EXPECTED_SHA256:
        print("error: archive sha256 != fetch_epc.EXPECTED_SHA256 (new release?)", file=sys.stderr)
        return 1
    retrieved = datetime.fromtimestamp(ARCHIVE.stat().st_mtime).date()
    document = build_document(iter_rows(csvs), retrieved=retrieved, archive_sha256=digest)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(to_yaml(document), encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT} from {len(csvs)} CSV file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
