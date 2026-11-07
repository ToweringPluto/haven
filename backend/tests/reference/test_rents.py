"""Private Sector Rent Statistics (Lothian BRMA) reference data: YAML, schema and parser."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from haven.reference import RentReference, RentStatistics, load_rents
from scripts import ingest_rents as ingest
from scripts.ingest_rents import (
    METHODOLOGY_URL,
    RAW_CSV,
    SOURCE_URL,
    IngestError,
    parse_csv,
    parse_source,
    read_csv,
)


@pytest.fixture(scope="module")
def reference() -> RentReference:
    return load_rents()


def test_committed_values(reference: RentReference) -> None:
    # Private Rents Open Data CSV, Lothian, 2025 (year to end September 2025).
    assert reference.year == 2025
    assert reference.period_end == date(2025, 9, 30)
    assert reference.published == date(2025, 11, 25)
    assert reference.rents.bedrooms_2 == RentStatistics(
        lower_quartile_gbp_pcm=1150,
        median_gbp_pcm=1325,
        mean_gbp_pcm=1356.43,
        upper_quartile_gbp_pcm=1500,
        n_records=3346,
    )
    assert reference.rents.bedrooms_1.median_gbp_pcm == 1000
    assert reference.rents.shared_1_bedroom.median_gbp_pcm == 630


def test_medians_rise_with_bedrooms(reference: RentReference) -> None:
    medians = [reference.for_bedrooms(n) for n in (1, 2, 3, 4)]
    values = [m.median_gbp_pcm for m in medians if m is not None]
    assert len(values) == 4
    assert values == sorted(values)
    assert reference.rents.shared_1_bedroom.median_gbp_pcm < values[0]


def test_unpublished_sizes_are_insufficient(reference: RentReference) -> None:
    assert reference.for_bedrooms(0) is None
    assert reference.for_bedrooms(5) is None
    assert reference.for_bedrooms(2) is reference.rents.bedrooms_2


def test_method_and_scope_stated(reference: RentReference) -> None:
    assert reference.basis == "mostly_advertised_rents"
    assert reference.unit == "gbp_per_calendar_month"
    notes = reference.meta.notes
    assert "advertised rents" in notes
    assert "wider than the City of Edinburgh" in notes
    assert "not a valuation" in notes


def test_provenance_points_at_gov_scot(reference: RentReference) -> None:
    assert reference.meta.source_url == SOURCE_URL == reference.source_url
    assert reference.methodology_url == METHODOLOGY_URL
    assert "Open Government Licence v3.0" in reference.meta.licence


def test_reparse_raw_csv_matches_yaml(reference: RentReference) -> None:
    if not RAW_CSV.is_file():
        pytest.skip("raw rents CSV not present (run ingest_rents.py --download)")
    assert parse_source() == reference.model_dump(mode="python", exclude={"meta"})


def test_check_mode_passes() -> None:
    assert ingest.main(["--check"]) == 0


# --- schema --------------------------------------------------------------------------------


def test_quartiles_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="lower quartile <= median"):
        RentStatistics(
            lower_quartile_gbp_pcm=1500,
            median_gbp_pcm=1325,
            mean_gbp_pcm=1356,
            upper_quartile_gbp_pcm=1600,
            n_records=10,
        )


def test_period_end_must_match_year(reference: RentReference) -> None:
    data = reference.model_dump(mode="json")
    data["period_end"] = "2025-12-31"
    with pytest.raises(ValidationError, match="30 September"):
        RentReference.model_validate(data)


def test_other_brma_rejected(reference: RentReference) -> None:
    data = reference.model_dump(mode="json")
    data["brma"] = "Greater Glasgow"
    with pytest.raises(ValidationError):
        RentReference.model_validate(data)


# --- CSV parser on synthetic text ----------------------------------------------------------

MEASURES = ("Lower Quartile", "Mean", "Median", "Number of Records", "Upper Quartile")
BEDS = ("1 Bedroom", "1 Bedroom Shared", "2 Bedroom", "3 Bedroom", "4 Bedroom")


def _csv(year_values: dict[int, float], *, brma: str = "Lothian", beds_shared: str = "") -> str:
    lines = ["﻿BRMA,Year,Measure,Beds,Value"]
    for year, base in year_values.items():
        for i, beds in enumerate(BEDS):
            label = beds_shared if beds_shared and "Shared" in beds else beds
            values = {
                "Lower Quartile": base + i * 100,
                "Median": base + i * 100 + 50,
                "Mean": base + i * 100 + 55.556,
                "Upper Quartile": base + i * 100 + 90,
                "Number of Records": 100 + i,
            }
            for measure in MEASURES:
                lines.append(f"Scotland,{year},{measure},{label},1")
                lines.append(f"{brma},{year},{measure},{label},{values[measure]}")
    return "\n".join(lines) + "\n"


def test_parse_picks_latest_lothian_year() -> None:
    year, rents = parse_csv(_csv({2024: 500, 2025: 700}))
    assert year == 2025
    assert rents["bedrooms_1"] == {
        "lower_quartile_gbp_pcm": 700.0,
        "median_gbp_pcm": 750.0,
        "mean_gbp_pcm": 755.56,
        "upper_quartile_gbp_pcm": 790.0,
        "n_records": 100,
    }
    assert rents["shared_1_bedroom"]["median_gbp_pcm"] == 850.0
    assert set(rents) == {
        "shared_1_bedroom",
        "bedrooms_1",
        "bedrooms_2",
        "bedrooms_3",
        "bedrooms_4",
    }


def test_parse_accepts_lower_case_shared_label() -> None:
    _, rents = parse_csv(_csv({2025: 700}, beds_shared="1 Bedroom shared"))
    assert rents["shared_1_bedroom"]["n_records"] == 101


def test_parse_rejects_na_value() -> None:
    text = _csv({2025: 700}).replace(
        "Lothian,2025,Median,3 Bedroom,1050", "Lothian,2025,Median,3 Bedroom,NA"
    )
    with pytest.raises(IngestError, match="not a number"):
        parse_csv(text)


def test_parse_rejects_missing_measure() -> None:
    lines = _csv({2025: 700}).splitlines()
    text = "\n".join(line for line in lines if not line.startswith("Lothian,2025,Mean,4 Bedroom,"))
    with pytest.raises(IngestError, match="bedrooms_4: missing mean_gbp_pcm"):
        parse_csv(text)


def test_parse_rejects_unknown_category() -> None:
    text = _csv({2025: 700}).replace("Lothian,2025,Median,4 Bedroom", "Lothian,2025,Median,Studio")
    with pytest.raises(IngestError, match="unknown category"):
        parse_csv(text)


def test_parse_rejects_missing_brma() -> None:
    with pytest.raises(IngestError, match="no rows"):
        parse_csv(_csv({2025: 700}, brma="Fife"))


def test_parse_rejects_bad_header() -> None:
    with pytest.raises(IngestError, match="header"):
        parse_csv("Area,Year,Measure,Beds,Value\n")


def test_missing_csv_reported(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="--download"):
        read_csv(tmp_path / "absent.csv")
