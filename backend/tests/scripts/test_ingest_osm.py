"""OSM + PHS GP ingest: parsing saved sample responses into location cache entries."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from haven.location import LocationCacheFile, PlaceKind, Point, RouteProfile, RouteResult
from haven.store import load_seed
from scripts import ingest_osm as ingest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "osm"
ORIGIN = Point(latitude=55.97217, longitude=-3.17449)  # seed-prop-leith
FETCHED = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def overpass() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "overpass_sample.json").read_text("utf-8"))
    return data


def test_query_covers_every_kind_and_radius() -> None:
    query = ingest.build_query(55.97, -3.17)
    assert query.startswith("[out:json]") and "out center tags;" in query
    assert query.count("(around:1500,55.97,-3.17)") == len(PlaceKind)
    assert '"amenity"="doctors"' in query and '"railway"="tram_stop"' in query


@pytest.mark.parametrize(
    ("tags", "kind"),
    [
        ({"highway": "bus_stop"}, PlaceKind.bus_stop),
        ({"railway": "tram_stop"}, PlaceKind.tram_stop),
        ({"railway": "station"}, PlaceKind.rail_station),
        ({"railway": "halt"}, PlaceKind.rail_station),
        ({"railway": "station", "station": "light_rail"}, None),
        ({"railway": "station", "tram": "yes"}, None),
        ({"railway": "station", "tram": "yes", "train": "yes"}, PlaceKind.rail_station),
        ({"shop": "supermarket"}, PlaceKind.supermarket),
        ({"amenity": "pharmacy"}, PlaceKind.pharmacy),
        ({"amenity": "doctors"}, PlaceKind.gp_surgery),
        ({"amenity": "school"}, PlaceKind.school),
        ({"public_transport": "station", "tram": "yes"}, None),
        ({"amenity": "cafe"}, None),
    ],
)
def test_classify(tags: dict[str, str], kind: PlaceKind | None) -> None:
    assert ingest.classify(tags) is kind


def test_parse_overpass_sample() -> None:
    found = ingest.parse_overpass(overpass(), ORIGIN, FETCHED)
    assert set(found) == set(PlaceKind)
    names = {kind: [p.name for p in places] for kind, places in found.items()}
    assert names[PlaceKind.bus_stop] == ["Great Junction Street"]  # "Too far" dropped
    assert names[PlaceKind.tram_stop] == ["Foot of the Walk"]  # stop position only
    assert names[PlaceKind.rail_station] == ["Example Rail"]  # light rail excluded
    assert names[PlaceKind.supermarket] == ["Example Foods"]  # way centre used
    assert names[PlaceKind.pharmacy] == [None]
    assert names[PlaceKind.school] == ["Example Primary"]  # way without centre skipped
    place = found[PlaceKind.gp_surgery][0]
    assert place.source == ingest.OSM_SOURCE
    assert place.source_ref == "osm:node/9"
    assert place.fetched_at == FETCHED
    assert 0 < place.distance_m <= ingest.RADIUS_M


def test_parse_overpass_rejects_partial_results() -> None:
    with pytest.raises(ingest.IngestError, match="remark"):
        ingest.parse_overpass({"elements": [], "remark": "runtime error: timeout"}, ORIGIN, FETCHED)
    with pytest.raises(ingest.IngestError, match="elements"):
        ingest.parse_overpass({}, ORIGIN, FETCHED)


def test_gp_practices_from_phs_csv() -> None:
    practices = ingest.read_gp_practices(FIXTURES / "gp_practices_sample.csv")
    assert [p.code for p in practices] == ["70001", "70002", "70003"]  # Lothian only
    assert practices[0].postcode == "EH6 6AA"  # normalised
    coords = ingest.parse_postcodes(json.loads((FIXTURES / "postcodes_sample.json").read_text()))
    assert "EH99 9ZZ" not in coords
    places = ingest.gp_places(practices, coords, ORIGIN, FETCHED)
    assert [p.name for p in places] == ["Near Practice"]  # far one outside 1500 m
    assert places[0].source_ref == "phs:gp_practice/70001"
    assert "postcode" in places[0].source


def test_gp_csv_missing_columns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("PracticeCode,Name\n1,x\n", encoding="utf-8")
    with pytest.raises(ingest.IngestError, match="lacks columns"):
        ingest.read_gp_practices(bad)


def test_build_cache_merges_gp_sources_and_keeps_routes() -> None:
    prop = load_seed().get("seed-prop-leith")
    assert prop is not None
    raw = {"fetched_at": FETCHED.isoformat(), "response": overpass()}
    practices = ingest.read_gp_practices(FIXTURES / "gp_practices_sample.csv")
    coords = ingest.parse_postcodes(json.loads((FIXTURES / "postcodes_sample.json").read_text()))
    gp = ingest.gp_places(practices, coords, ORIGIN, FETCHED)
    route = RouteResult(
        profile=RouteProfile.foot_walking,
        origin=ORIGIN,
        destination=Point(latitude=55.952, longitude=-3.189, name="Edinburgh Waverley"),
        status="known",
        distance_m=2500,
        duration_s=1800,
        source="openrouteservice",
        fetched_at=FETCHED,
    )
    existing = LocationCacheFile(property_id=prop.id, origin=ORIGIN, routes=[route])
    cache = ingest.build_cache(prop, raw, gp, FETCHED, existing)
    assert [e.kind for e in cache.nearby] == list(PlaceKind)
    gp_entry = next(e for e in cache.nearby if e.kind is PlaceKind.gp_surgery)
    assert gp_entry.source == ingest.GP_ENTRY_SOURCE
    assert {p.source_ref for p in gp_entry.places} == {"osm:node/9", "phs:gp_practice/70001"}
    assert cache.routes == [route]
    moved = existing.model_copy(update={"origin": Point(latitude=55.9, longitude=-3.1)})
    assert ingest.build_cache(prop, raw, gp, FETCHED, moved).routes == []


def test_check_reports_missing_cache(tmp_path: Path) -> None:
    props = load_seed().list()[:1]
    assert any("no cache file" in p for p in ingest.check(props, tmp_path))
