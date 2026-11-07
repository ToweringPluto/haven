"""Data layer: registry, seed files, loaders, reference JSON and the cached fetcher."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from haven.config import REFERENCE_JSON_DIR, REPO_ROOT
from haven.datasets import Integration, load_registry, load_seed_file, render_seed
from haven.datasets.loaders import LOADERS, LoaderSourceMissing, ofgem_cap
from haven.datasets.loaders.epc import estimate_heat_kwh
from haven.datasets.registry import TABLE_END, TABLE_START, render_markdown_table
from haven.datasets.seeds import write_seed
from haven.reference import load_energy_rates
from scripts import fetch_cached

REGISTRY = load_registry()


def _lothian_mean(year: int, beds: str) -> float:
    records = load_seed_file("private_rents").records
    (match,) = [r for r in records if r["year"] == year and r["beds"] == beds]
    value: float = match["mean_gbp_pcm"]
    return value


# --- Required checks ---------------------------------------------------------------------


@pytest.mark.parametrize("beds,expected", [("1_bed", 1057), ("2_bed", 1356)])
def test_lothian_mean_rent_year_to_sept_2025(beds: str, expected: float) -> None:
    mean = _lothian_mean(2025, beds)
    assert abs(mean - expected) <= 1, (
        f"STOP: Lothian {beds} mean for the year to Sept 2025 is {mean}, expected {expected} "
        "within £1. The CSV or its parsing has changed; inspect before going further."
    )


def test_lothian_1_bed_lha_monthly() -> None:
    records = load_seed_file("lha_rates").records
    (one_bed,) = [r for r in records if r["category"] == "1_bed"]
    assert one_bed["monthly_rate_gbp"] == 747.93
    assert one_bed["monthly_rate_gbp"] == round(one_bed["weekly_rate_gbp"] * 52 / 12, 2)


def test_every_registry_entry_has_url_licence_as_of() -> None:
    for entry in REGISTRY.datasets:
        assert entry.url.startswith(("http://", "https://")), entry.id
        assert entry.licence_note.strip(), entry.id
        assert isinstance(entry.as_of, date), entry.id


def test_no_sample_flat_has_is_sample_false() -> None:
    records = load_seed_file("sample_flats").records
    assert len(records) >= 18
    assert all(r["is_sample"] is True for r in records)


# --- Registry ----------------------------------------------------------------------------


def test_registry_seed_paths_exist() -> None:
    for entry in REGISTRY.datasets:
        assert entry.seed, f"{entry.id}: no offline seed/reference/cache path"
        assert (REPO_ROOT / entry.seed).exists(), f"{entry.id}: {entry.seed} missing"


def test_every_loader_is_registered_and_dates_agree() -> None:
    for dataset_id in LOADERS:
        entry = REGISTRY.get(dataset_id)
        seed = load_seed_file(dataset_id)
        assert seed.as_of == entry.as_of, dataset_id
        assert seed.retrieved_at == entry.retrieved_at, dataset_id


def test_sample_integrations_are_all_sample_records() -> None:
    for entry in REGISTRY.datasets:
        if entry.integration is Integration.sample:
            assert all(r["is_sample"] for r in load_seed_file(entry.id).records), entry.id


def test_readme_table_matches_registry() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert TABLE_START in readme and TABLE_END in readme
    assert render_markdown_table(REGISTRY) in readme, "run scripts/render_registry.py"


# --- Seeds -------------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_id", list(LOADERS))
def test_seed_is_up_to_date_and_flags_samples(dataset_id: str) -> None:
    committed = load_seed_file(dataset_id)
    assert all(isinstance(r["is_sample"], bool) for r in committed.records)
    try:
        built = LOADERS[dataset_id].build()
    except LoaderSourceMissing:
        pytest.skip("raw source not present; committed seed is the fallback")
    assert render_seed(built) == render_seed(committed), "run scripts/build_seeds.py"


def test_seed_writing_is_idempotent(tmp_path: Path) -> None:
    document = LOADERS["lha_rates"].build()
    assert write_seed(document, tmp_path) is True
    assert write_seed(document, tmp_path) is False


def test_real_data_seeds_are_not_marked_sample() -> None:
    for dataset_id in ("private_rents", "lha_rates", "council_tax", "ofgem_cap", "epc"):
        assert not any(r["is_sample"] for r in load_seed_file(dataset_id).records), dataset_id


def test_ofgem_config_matches_ingested_rates_for_same_period() -> None:
    config, ingested = ofgem_cap.load_config(), load_energy_rates()
    if (config.valid_from, config.valid_to) != (ingested.valid_from, ingested.valid_to):
        pytest.skip("config describes a different cap period than energy_rates.yaml")
    for fuel in ("electricity", "gas"):
        a, b = getattr(config, fuel), getattr(ingested, fuel)
        assert a.unit_rate_p_per_kwh == b.unit_rate_p_per_kwh, fuel
        assert a.standing_charge_p_per_day == b.standing_charge_p_per_day, fuel


def test_council_tax_seed_band_d() -> None:
    records = load_seed_file("council_tax").records
    (band_d,) = [r for r in records if r["band"] == "D"]
    assert band_d["year"] == "2026/27"
    assert band_d["annual_total_gbp"] == 2278.37


def test_epc_lookup_scales_by_floor_area_and_falls_back() -> None:
    records = load_seed_file("epc").records
    band_c = next(r for r in records if r["level"] == "band" and r["epc_band"] == "C")
    est = estimate_heat_kwh(records, "C", 50)
    assert est is not None and est["level"] == "band"
    assert est["median_kwh"] == round(band_c["median_kwh_per_m2"] * 50)
    assert estimate_heat_kwh(records, "Z", 50) is None


def test_epc_seed_has_no_address_fields() -> None:
    keys = {k.lower() for r in load_seed_file("epc").records for k in r}
    assert not keys & {"address", "address1", "address2", "postcode", "post_town", "uprn"}
    assert keys == {
        "level",
        "epc_band",
        "property_type",
        "main_fuel",
        "n",
        "median_kwh_per_m2",
        "q1_kwh_per_m2",
        "q3_kwh_per_m2",
        "is_sample",
    }


def test_landlord_numbers_are_obviously_fake() -> None:
    numbers = {r["registration_number"] for r in load_seed_file("landlord_register").records}
    assert all(n.startswith("SAMPLE-") for n in numbers)
    flats = load_seed_file("sample_flats").records
    assert {f["landlord_registration_number"] for f in flats} <= numbers


def test_rent_sql_is_idempotent_ddl() -> None:
    sql = (REPO_ROOT / "data" / "sql" / "rent_stats.sql").read_text(encoding="utf-8")
    assert "create_hypertable('rent_stats', 'period_end', if_not_exists => TRUE" in sql
    assert "CREATE TABLE IF NOT EXISTS rent_stats" in sql
    assert "ON CONFLICT (brma, beds, period_end) DO UPDATE" in sql


# --- Reference JSON ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "dataset_id,label",
    [("handbook_4_2", "guidance value"), ("repairing_standard", "reference only")],
)
def test_reference_json_is_labelled_never_a_legal_test(dataset_id: str, label: str) -> None:
    data: dict[str, Any] = json.loads(
        (REFERENCE_JSON_DIR / f"{dataset_id}.json").read_text(encoding="utf-8")
    )
    assert data["label"] == label
    assert "never a legal test" in data["legal_status"].lower()
    assert data["items"]
    assert all(item["label"] == label and item["is_sample"] is False for item in data["items"])
    assert date.fromisoformat(data["as_of"]) == REGISTRY.get(dataset_id).as_of


# --- Cached fetcher ----------------------------------------------------------------------


def test_fetcher_only_plans_demo_areas_and_one_naptan_request() -> None:
    requests = fetch_cached.planned_requests()
    overpass = {r.area for r in requests if r.source == "overpass"}
    naptan = [r for r in requests if r.source == "naptan"]
    assert overpass == {"leith", "marchmont", "gorgie"}
    assert len(naptan) == 1 and naptan[0].params["atcoAreaCodes"] == "620"
    assert all("nominatim" not in r.url for r in requests)
    assert "haven" in fetch_cached.USER_AGENT and len(fetch_cached.USER_AGENT) > 30


def test_fetcher_never_refetches_cached_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_cached, "CACHE_DIR", tmp_path)
    for request in fetch_cached.planned_requests():
        target = (
            tmp_path / request.source / f"{request.area}_{request.query_hash}_20260101T000000Z.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")

    def boom(*_: Any, **__: Any) -> Path:
        raise AssertionError("fetch called although the cache exists")

    monkeypatch.setattr(fetch_cached, "fetch", boom)
    assert fetch_cached.main([]) == 0
