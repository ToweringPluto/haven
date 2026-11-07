"""EPC ingest: parsing, fuel/type mapping, dedupe and aggregation on a synthetic CSV."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from haven.domain import EpcBand, MainFuel, PropertyType
from haven.reference import EnergyModelReference
from scripts import ingest_epc as ingest
from scripts.ingest_epc import Record, aggregate, build_document, collect, iter_rows, map_main_fuel

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "epc_synthetic.csv"
SHA = "0" * 64


def _rows() -> list[dict[str, str]]:
    return list(iter_rows([FIXTURE]))


def _document(min_n: int = 3) -> dict[str, Any]:
    return build_document(_rows(), retrieved=date(2026, 11, 7), archive_sha256=SHA, min_n=min_n)


def test_iter_rows_skips_label_row_and_reads_only_needed_columns() -> None:
    rows = _rows()
    assert len(rows) == 18
    assert rows[0]["BUILDING_REFERENCE_NUMBER"] == "1001"
    assert all("ADDRESS1" not in r for r in rows)
    assert set(rows[0]) == set(ingest.COLUMNS)


def test_iter_rows_handles_bom_and_missing_columns(tmp_path: Path) -> None:
    good = tmp_path / "bom.csv"
    good.write_bytes(b"\xef\xbb\xbf" + FIXTURE.read_bytes())
    assert len(list(iter_rows([good]))) == 18

    bad = tmp_path / "bad.csv"
    bad.write_text("BUILDING_REFERENCE_NUMBER,LODGEMENT_DATE\nlabel,label\n1,2024-01-01\n")
    with pytest.raises(SystemExit, match="missing column"):
        list(iter_rows([bad]))


@pytest.mark.parametrize(
    ("main_fuel", "description", "expected"),
    [
        ("mains gas (not community)", "", MainFuel.mains_gas),
        ("Gas: mains gas", "", MainFuel.mains_gas),
        ("electricity (not community)", "", MainFuel.electricity),
        ("Electricity: electricity, unspecified tariff", "", MainFuel.electricity),
        ("mains gas (community)", "", MainFuel.other),
        ("electricity (community)", "", MainFuel.other),
        ("oil (not community)", "", MainFuel.other),
        ("LPG (not community)", "", MainFuel.other),
        ("no heating/hot-water system or data is from a community network", "", None),
        ("", "Boiler and radiators, mains gas | Room heaters, electric ", MainFuel.mains_gas),
        ("", "Electric storage heaters ", MainFuel.electricity),
        ("", "Air source heat pump, radiators, electric ", MainFuel.electricity),
        ("", "Community scheme ", MainFuel.other),
        ("", "Boiler and radiators, oil ", MainFuel.other),
        ("", "", None),
    ],
)
def test_map_main_fuel(main_fuel: str, description: str, expected: MainFuel | None) -> None:
    assert map_main_fuel(main_fuel, description) is expected


def test_collect_filters_dedupes_and_counts_exclusions() -> None:
    collected = collect(_rows())
    assert collected.read == 17  # the Glasgow City row is not counted
    assert collected.duplicates_removed == 1
    assert dict(collected.excluded) == {
        "invalid_epc_band": 1,
        "invalid_floor_area": 2,
        "invalid_heat_demand": 1,
    }
    by_ref = {r.building_ref: r for r in collected.records}
    assert len(collected.records) == 12
    assert by_ref["1005"].lodged == "2024-05-10"  # the later certificate wins
    assert by_ref["1005"].kwh_per_m2 == pytest.approx(140.0)
    assert by_ref["1004"].main_fuel is MainFuel.mains_gas  # from MAINHEAT_DESCRIPTION
    assert by_ref["1017"].property_type is PropertyType.other
    assert by_ref["1017"].main_fuel is None


def test_dedupe_keeps_latest_regardless_of_file_order() -> None:
    rows = _rows()
    collected = collect(list(reversed(rows)))
    by_ref = {r.building_ref: r for r in collected.records}
    assert by_ref["1005"].lodged == "2024-05-10"


def test_aggregate_band_and_detail_groups() -> None:
    bands, groups = aggregate(collect(_rows()).records, min_n=3)
    assert bands == [
        {"epc_band": "C", "n": 4, "median": 85.0, "q1": 75.0, "q3": 92.5},
        {"epc_band": "D", "n": 7, "median": 130.0, "q1": 115.0, "q3": 170.0},
    ]  # band B has n=1 < 3 and is dropped
    assert groups == [
        {
            "epc_band": "C",
            "property_type": "house",
            "main_fuel": "mains_gas",
            "n": 3,
            "median": 90.0,
            "q1": 85.0,
            "q3": 95.0,
        },
        {
            "epc_band": "D",
            "property_type": "flat",
            "main_fuel": "mains_gas",
            "n": 5,
            "median": 120.0,
            "q1": 110.0,
            "q3": 130.0,
        },
    ]  # D/flat/electricity (n=2) and C/flat/other (n=1) fall back to their bands


def test_default_threshold_is_30() -> None:
    def rec(i: int, fuel: MainFuel) -> Record:
        return Record(str(i), "2024-01-01", "", EpcBand.E, PropertyType.flat, fuel, float(i))

    records = [rec(i, MainFuel.mains_gas) for i in range(30)]
    records += [rec(100 + i, MainFuel.electricity) for i in range(29)]
    bands, groups = aggregate(records)
    assert ingest.MIN_GROUP_N == 30
    assert [b["n"] for b in bands] == [59]
    assert [(g["main_fuel"], g["n"]) for g in groups] == [("mains_gas", 30)]


def test_build_document_validates_and_records_provenance() -> None:
    doc = _document()
    model = EnergyModelReference.model_validate(doc)
    assert model.meta.source_url == ingest.DATASET_URL
    assert model.lighting_included is False
    assert model.numerator_columns == ["SPACE_HEATING_DEMAND", "WATER_HEATING_DEMAND"]
    assert model.records.used == 12
    assert model.records.without_main_fuel == 1
    assert model.records.without_property_type == 0
    assert "Lighting is NOT included" in model.meta.notes


def test_lookup_falls_back_to_band_then_none() -> None:
    model = EnergyModelReference.model_validate(_document())
    exact = model.lookup(EpcBand.D, PropertyType.flat, MainFuel.mains_gas)
    assert exact is not None and exact.level == "band_type_fuel"
    assert exact.distribution.median == 120.0

    fallback = model.lookup(EpcBand.D, PropertyType.flat, MainFuel.electricity)
    assert fallback is not None and fallback.level == "band"
    assert fallback.distribution.median == 130.0

    unknown_type = model.lookup(EpcBand.D, None, MainFuel.mains_gas)
    assert unknown_type is not None and unknown_type.level == "band"

    assert model.lookup(EpcBand.B, PropertyType.other, MainFuel.other) is None
    assert model.lookup(EpcBand.G) is None


def test_schema_rejects_small_groups_and_inconsistent_counts() -> None:
    doc = _document()
    with pytest.raises(ValidationError, match="min_group_n"):
        EnergyModelReference.model_validate({**doc, "min_group_n": 30})
    bad_counts = {**doc, "records": {**doc["records"], "used": 13}}
    with pytest.raises(ValidationError, match="must equal used"):
        EnergyModelReference.model_validate(bad_counts)
    bad_order = {**doc, "band_groups": [{**doc["band_groups"][0], "q1": 999.0}]}
    with pytest.raises(ValidationError, match="q1 <= median"):
        EnergyModelReference.model_validate(bad_order)


def test_yaml_round_trip(tmp_path: Path) -> None:
    from haven.reference import load_reference_file

    path = tmp_path / "energy_kwh_per_m2_edinburgh.yaml"
    path.write_text(ingest.to_yaml(_document()), encoding="utf-8")
    loaded = load_reference_file(path, EnergyModelReference)
    assert loaded == EnergyModelReference.model_validate(_document())


def test_check_validates_committed_file() -> None:
    assert ingest.main(["--check"]) == 0


def test_committed_file_is_plausible() -> None:
    from haven.reference import load_energy_model

    model = load_energy_model()
    assert model.lighting_included is False
    assert [b.epc_band for b in model.band_groups] == list(EpcBand)
    # Worse EPC bands should need more heat per m² (B to G; band A mixes few, unusual homes).
    medians = [b.median for b in model.band_groups[1:]]
    assert medians == sorted(medians)
    assert all(g.n >= model.min_group_n for g in [*model.band_groups, *model.groups])
    flat_gas_d = model.lookup(EpcBand.D, PropertyType.flat, MainFuel.mains_gas)
    assert flat_gas_d is not None and flat_gas_d.level == "band_type_fuel"
