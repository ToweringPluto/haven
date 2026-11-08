"""Seed properties: generated file, edge cases, provenance, store and API wiring."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.engines import EngineBackend
from haven.api.fixtures import FixtureBackend
from haven.config import CONTRACT_EXAMPLES_DIR, SEED_PATH
from haven.cost import estimate_monthly_cost, load_cost_references
from haven.domain import (
    BudgetComparison,
    MainFuel,
    Origin,
    Property,
    PropertyType,
    Status,
)
from haven.location.geo import haversine_m
from haven.reference import load_energy_model
from haven.store import ILLUSTRATIVE_TITLE_PREFIX, SeedDataError, SeedFile, SeedStore, load_seed
from scripts import make_seed

ON = date(2026, 11, 7)  # inside the reference periods on file
NEIGHBOURHOODS = {
    "Leith",
    "Marchmont",
    "Gorgie",
    "Portobello",
    "Old Town",
    "Craigleith",
    "Gilmerton",
    "Bruntsfield",
    "Dalry",
    "Sighthill",
    "Wester Hailes",
}
# Generous City of Edinburgh bounding box.
LAT_RANGE = (55.85, 56.00)
LON_RANGE = (-3.40, -3.05)
EVIDENCE_FIELDS = [
    name
    for name, info in Property.model_fields.items()
    if getattr(info.annotation, "__name__", "").startswith("Evidence")
]


@pytest.fixture(scope="module")
def store() -> SeedStore:
    return load_seed()


@pytest.fixture(scope="module")
def props(store: SeedStore) -> list[Property]:
    return store.list()


def by_id(props: list[Property], slug: str) -> Property:
    return next(p for p in props if p.id == f"seed-prop-{slug}")


# --- the file --------------------------------------------------------------------------


def test_seed_file_is_up_to_date() -> None:
    assert make_seed.main(["--check"]) == 0


def test_generator_is_deterministic() -> None:
    assert make_seed.render(make_seed.build_seed()) == make_seed.render(make_seed.build_seed())


def test_fictional_properties_cover_the_named_neighbourhoods(props: list[Property]) -> None:
    assert len(props) == 48
    assert {p.area for p in props} >= NEIGHBOURHOODS
    for p in props:
        assert p.illustrative is True
        assert p.title.startswith(f"{ILLUSTRATIVE_TITLE_PREFIX}: ")


def test_homes_are_spread_out_so_map_pins_stay_readable(props: list[Property]) -> None:
    points = [(p.latitude, p.longitude) for p in props]
    for i, (lat1, lon1) in enumerate(points):
        assert lat1 is not None and lon1 is not None
        for lat2, lon2 in points[i + 1 :]:
            assert lat2 is not None and lon2 is not None
            assert haversine_m(lat1, lon1, lat2, lon2) >= 650


def test_coordinates_are_street_points_in_edinburgh(props: list[Property]) -> None:
    for p in props:
        assert p.latitude is not None and p.longitude is not None
        assert LAT_RANGE[0] < p.latitude < LAT_RANGE[1]
        assert LON_RANGE[0] < p.longitude < LON_RANGE[1]
        # No house numbers: the area is a neighbourhood name only.
        assert p.area is not None and not any(ch.isdigit() for ch in p.area)
    assert len({(p.latitude, p.longitude) for p in props}) == len(props)


def test_raw_yaml_has_no_address_fields() -> None:
    raw = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    for item in raw["properties"]:
        assert not {"address", "postcode", "house_number", "street"} & set(item)


def test_every_fact_carries_seed_provenance(props: list[Property]) -> None:
    assert EVIDENCE_FIELDS  # sanity: the introspection found the Evidence fields
    for p in props:
        evidence = [getattr(p, name) for name in EVIDENCE_FIELDS]
        evidence += [c.monthly_gbp for c in p.other_recurring_costs]
        for ev in evidence:
            assert ev.origin is Origin.listing
            assert ev.source == make_seed.SOURCE
            assert ev.as_of == make_seed.GENERATED_ON
            assert ev.note
            assert ev.status in (Status.known, Status.insufficient)


def test_meta_records_sources(store: SeedStore) -> None:
    meta = store.meta
    assert "energy_kwh_per_m2_edinburgh" in meta.epc_distribution_source
    assert "ODbL" in meta.coordinates_licence
    assert "openstreetmap" in meta.coordinates_source.lower()
    assert meta.coordinates_retrieved <= date.today()
    assert set(meta.edge_cases) <= {p.id for p in store}
    assert len(meta.edge_cases) == 8


# --- EPC mix is drawn from the Edinburgh EPC distribution ------------------------------


def test_epc_band_type_fuel_combinations_exist_in_the_edinburgh_epc_groups(
    props: list[Property],
) -> None:
    groups = {(g.epc_band, g.property_type, g.main_fuel) for g in load_energy_model().groups}
    for p in props:
        key = (p.epc_rating.value, p.property_type.value, p.main_fuel.value)
        assert key in groups, p.id


def test_draw_group_is_weighted_and_respects_fixed_fields() -> None:
    import random

    groups = load_energy_model().groups
    rng = random.Random(0)
    draws = [make_seed.draw_group(rng, groups, "flat", None) for _ in range(2000)]
    assert all(g.property_type is PropertyType.flat for g in draws)
    share_c = sum(g.epc_band.value == "C" for g in draws) / len(draws)
    flats = [g for g in groups if g.property_type is PropertyType.flat]
    expected_c = sum(g.n for g in flats if g.epc_band.value == "C") / sum(g.n for g in flats)
    assert abs(share_c - expected_c) < 0.05
    fixed = make_seed.draw_group(random.Random(1), groups, "flat", "F")
    assert (fixed.epc_band.value, fixed.property_type) == ("F", PropertyType.flat)
    with pytest.raises(ValueError, match="no EPC group"):
        make_seed.draw_group(rng, groups, "flat", "Z")


# --- deliberate edge cases -------------------------------------------------------------


def test_edge_case_steps_and_third_floor_without_lift(props: list[Property]) -> None:
    p = by_id(props, "leith")
    assert p.entrance_steps.value and p.entrance_steps.value > 0
    assert p.floor_level.value is not None and p.floor_level.value >= 3
    assert p.has_lift.value is False and p.has_lift.status is Status.known


def test_edge_case_cheap_rent_but_epc_f(props: list[Property]) -> None:
    p = by_id(props, "gorgie")
    assert p.epc_rating.value == "F"
    assert p.rent_pcm_gbp.value is not None and p.rent_pcm_gbp.value < 750


def test_low_budget_demo_homes(props: list[Property]) -> None:
    """Three homes under £700 a month, one of them step-free, for lower-budget demos."""
    low = [p for p in props if (p.rent_pcm_gbp.value or 10_000) < 700]
    assert {p.id for p in low} == {
        "seed-prop-dalry",
        "seed-prop-sighthill",
        "seed-prop-wester-hailes",
    }
    sighthill = by_id(props, "sighthill")
    rents = [q.rent_pcm_gbp.value for q in props if q.rent_pcm_gbp.value is not None]
    assert sighthill.rent_pcm_gbp.value == min(rents)
    assert sighthill.entrance_steps.value == 0


def test_edge_case_missing_council_tax_band(props: list[Property]) -> None:
    p = by_id(props, "marchmont")
    assert p.council_tax_band.value is None
    assert p.council_tax_band.status is Status.insufficient
    assert [q.id for q in props if q.council_tax_band.value is None] == [p.id]


def test_edge_case_missing_lift_info(props: list[Property]) -> None:
    p = by_id(props, "old-town")
    assert p.has_lift.value is None and p.has_lift.status is Status.insufficient
    assert p.floor_level.value is not None and p.floor_level.value > 0
    assert p.has_lift.note and "lift" in p.has_lift.note


def test_edge_case_step_free_new_build(props: list[Property]) -> None:
    p = by_id(props, "craigleith")
    assert "new-build" in p.title
    assert p.entrance_steps.value == 0
    assert p.floor_level.value == 0 or p.has_lift.value is True
    assert p.epc_rating.value in ("A", "B")


def test_houses_are_ground_level(props: list[Property]) -> None:
    for p in props:
        if p.property_type.value in (PropertyType.house, PropertyType.bungalow):
            assert p.floor_level.value == 0


# --- the cost engine runs on every seed property ---------------------------------------


def test_cost_engine_handles_every_seed_property(props: list[Property]) -> None:
    refs = load_cost_references()
    for p in props:
        cost = estimate_monthly_cost(p, None, on=ON, references=refs)
        assert cost.budget_comparison is BudgetComparison.unknown
        heating_known = p.main_fuel.value is not MainFuel.other
        if p.council_tax_band.value is None or not heating_known:
            assert cost.total_monthly_gbp.status is Status.insufficient, p.id
        else:
            assert cost.total_monthly_gbp.value is not None, p.id


# --- the store -------------------------------------------------------------------------


def _write(tmp_path: Path, data: Any) -> Path:
    path = tmp_path / "properties.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    return data


def test_store_get_and_iteration(store: SeedStore) -> None:
    assert len(store) == 48
    first = store.list()[0]
    assert store.get(first.id) == first
    assert store.get("seed-prop-nowhere") is None
    assert [p.id for p in store] == [p.id for p in store.list()]


def test_store_rejects_duplicate_ids(tmp_path: Path) -> None:
    data = _raw()
    data["properties"].append(data["properties"][0])
    with pytest.raises(SeedDataError, match="duplicate"):
        load_seed(_write(tmp_path, data))


def test_store_rejects_non_illustrative_properties(tmp_path: Path) -> None:
    data = _raw()
    data["properties"][0]["illustrative"] = False
    with pytest.raises(SeedDataError, match="illustrative"):
        load_seed(_write(tmp_path, data))
    data = _raw()
    data["properties"][0]["title"] = "2-bed flat, Leith"
    with pytest.raises(SeedDataError, match="illustrative"):
        load_seed(_write(tmp_path, data))


def test_store_reports_missing_and_invalid_files(tmp_path: Path) -> None:
    with pytest.raises(SeedDataError, match="cannot read"):
        load_seed(tmp_path / "absent.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("properties: [", encoding="utf-8")
    with pytest.raises(SeedDataError, match="invalid YAML"):
        load_seed(bad)


# --- API -------------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(backend=EngineBackend(CONTRACT_EXAMPLES_DIR, today=lambda: ON)))


def test_list_properties_serves_the_seed_first(client: TestClient, store: SeedStore) -> None:
    response = client.get("/v1/properties")
    assert response.status_code == 200
    items = response.json()["items"]
    seed = [p.model_dump(mode="json") for p in store]
    assert items[: len(seed)] == seed
    # The persona fixture properties stay available for the fixture suitability pairs.
    assert {"ill-prop-leith-flat", "ill-prop-marchmont-flat", "ill-prop-gorgie-flat"} <= {
        i["id"] for i in items
    }


def test_get_seed_property_and_its_cost(client: TestClient, store: SeedStore) -> None:
    prop = store.list()[0]
    response = client.get(f"/v1/properties/{prop.id}")
    assert response.status_code == 200
    assert Property.model_validate(response.json()) == prop
    cost = client.post(f"/v1/properties/{prop.id}/cost", json={})
    assert cost.status_code == 200, cost.text
    expected = estimate_monthly_cost(prop, None, on=ON, references=load_cost_references())
    assert cost.json() == expected.model_dump(mode="json")


def test_default_app_serves_the_seed_from_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _raw()
    data["properties"] = data["properties"][:1]
    monkeypatch.setenv("HAVEN_SEED_PATH", str(_write(tmp_path, data)))
    items = TestClient(create_app()).get("/v1/properties").json()["items"]
    assert [i["id"] for i in items if i["id"].startswith("seed-")] == ["seed-prop-leith"]


def test_fixtures_backend_does_not_serve_the_seed() -> None:
    app = create_app(backend=FixtureBackend(CONTRACT_EXAMPLES_DIR))
    items = TestClient(app).get("/v1/properties").json()["items"]
    assert not [i for i in items if i["id"].startswith("seed-")]


def test_engine_backend_rejects_id_clash(store: SeedStore) -> None:
    clash = store.list()[0].model_copy(update={"id": "ill-prop-leith-flat"})
    seed = SeedStore(SeedFile.model_validate({"meta": store.meta, "properties": [clash]}))
    with pytest.raises(ValueError, match="clash"):
        EngineBackend(CONTRACT_EXAMPLES_DIR, seed=seed)
