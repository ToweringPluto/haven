"""``epc``: heat-demand lookup by EPC band, property type and heating fuel (Edinburgh).

Built from ``data/reference/energy_kwh_per_m2_edinburgh.yaml``, which
``scripts/ingest_epc.py`` aggregates from the Scottish domestic EPC register using
**non-address fields only** (``CURRENT_ENERGY_RATING``, ``PROPERTY_TYPE``, ``MAIN_FUEL`` /
``MAINHEAT_DESCRIPTION``, ``TOTAL_FLOOR_AREA``, heating demand columns). Address fields are
Royal Mail copyright with restricted use, and are never read or stored.

Each record is kWh per m² per year (space + water heating demand, SAP-modelled), so a bill
estimate is ``kwh_per_m2 * floor_area_m2 * unit_rate`` plus standing charges. See
:func:`estimate_heat_kwh`.
"""

from datetime import date
from typing import Any

from haven.datasets.seeds import SeedDocument, seed_document
from haven.reference import load_energy_model

DATASET_ID = "epc"


def build() -> SeedDocument:
    model = load_energy_model()
    records: list[dict[str, Any]] = []
    for g in model.groups:
        records.append(
            {
                "level": "band_type_fuel",
                "epc_band": g.epc_band.value,
                "property_type": g.property_type.value,
                "main_fuel": g.main_fuel.value,
                "n": g.n,
                "median_kwh_per_m2": g.median,
                "q1_kwh_per_m2": g.q1,
                "q3_kwh_per_m2": g.q3,
                "is_sample": False,
            }
        )
    for b in model.band_groups:
        records.append(
            {
                "level": "band",
                "epc_band": b.epc_band.value,
                "property_type": None,
                "main_fuel": None,
                "n": b.n,
                "median_kwh_per_m2": b.median,
                "q1_kwh_per_m2": b.q1,
                "q3_kwh_per_m2": b.q3,
                "is_sample": False,
            }
        )
    release_end = _release_end(model.dataset_release)
    return seed_document(
        DATASET_ID,
        source_url=model.meta.source_url,
        as_of=release_end,
        retrieved_at=model.meta.retrieved,
        licence_note=model.meta.licence,
        records=records,
    )


def _release_end(release: str) -> date:
    """Last day of the release's final quarter, e.g. 'Q4 2016 to Q3 2026 ...' -> 2026-09-30."""
    parts = release.split(" to ")[1].split()
    quarter, year = int(parts[0][1]), int(parts[1])
    month = quarter * 3
    day = 31 if month in (3, 12) else 30
    return date(year, month, day)


def estimate_heat_kwh(
    records: list[dict[str, Any]],
    epc_band: str,
    floor_area_m2: float,
    property_type: str | None = None,
    main_fuel: str | None = None,
) -> dict[str, Any] | None:
    """Annual heat demand (kWh) for a home: median and interquartile range.

    Uses the band x type x fuel group when it exists, else the band-only fallback; returns
    ``None`` when neither exists (treat as insufficient, never a default).
    """
    match = None
    if property_type and main_fuel:
        match = next(
            (
                r
                for r in records
                if r["level"] == "band_type_fuel"
                and (r["epc_band"], r["property_type"], r["main_fuel"])
                == (epc_band, property_type, main_fuel)
            ),
            None,
        )
    if match is None:
        match = next(
            (r for r in records if r["level"] == "band" and r["epc_band"] == epc_band), None
        )
    if match is None:
        return None
    return {
        "level": match["level"],
        "median_kwh": round(match["median_kwh_per_m2"] * floor_area_m2),
        "q1_kwh": round(match["q1_kwh_per_m2"] * floor_area_m2),
        "q3_kwh": round(match["q3_kwh_per_m2"] * floor_area_m2),
        "n": match["n"],
    }
