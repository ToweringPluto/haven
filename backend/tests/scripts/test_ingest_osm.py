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


# --- access tags (kerbs, inclines, surfaces, crossings) ----------------------------------

ACCESS_RESPONSE: dict[str, Any] = {
    "elements": [
        {"type": "way", "id": 1, "tags": {"highway": "footway", "surface": "asphalt"}},
        {"type": "way", "id": 2, "tags": {"highway": "steps", "incline": "up"}},
        {"type": "way", "id": 3, "tags": {"highway": "residential", "sidewalk": "both"}},
        {"type": "node", "id": 10, "tags": {"kerb": "lowered"}},
        {"type": "node", "id": 11, "tags": {"kerb": "raised", "barrier": "kerb"}},
        {"type": "node", "id": 12, "tags": {"barrier": "kerb"}},
        {"type": "node", "id": 13, "tags": {"kerb": "rolled"}},
        {"type": "node", "id": 14, "tags": {"highway": "crossing", "tactile_paving": "yes"}},
        {"type": "node", "id": 15, "tags": {"highway": "crossing", "kerb": "flush"}},
    ]
}


def test_access_query_asks_for_kerbs_crossings_and_pedestrian_ways() -> None:
    query = ingest.build_access_query(55.97, -3.17)
    assert "around:500,55.97,-3.17" in query
    assert '["kerb"]' in query and '["barrier"="kerb"]' in query
    assert '["highway"="crossing"]' in query and "steps" in query


def test_summarise_access_counts_tags() -> None:
    summary = ingest.summarise_access(ACCESS_RESPONSE, FETCHED)
    assert summary.ways == 3 and summary.steps_ways == 1
    assert summary.ways_with_surface == 1 and summary.ways_with_incline == 1
    assert summary.ways_with_sidewalk == 1 and summary.ways_with_smoothness == 0
    assert summary.crossings == 2 and summary.crossings_with_tactile_paving == 1
    k = summary.kerbs
    assert (k.lowered, k.raised, k.flush, k.other, k.untagged, k.no) == (1, 1, 1, 1, 1, 0)
    assert summary.coverage("surface") == pytest.approx(1 / 3)


def test_summarise_access_rejects_partial_results() -> None:
    with pytest.raises(ingest.IngestError):
        ingest.summarise_access({"elements": [], "remark": "runtime error: timeout"}, FETCHED)


def test_enrich_adds_access_without_touching_places_or_routes() -> None:
    cache = LocationCacheFile(
        property_id="p",
        origin=ORIGIN,
        routes=[
            RouteResult(
                profile=RouteProfile.wheelchair,
                origin=ORIGIN,
                destination=Point(latitude=55.95, longitude=-3.19, name="Waverley"),
                status="known",
                distance_m=2400,
                source="openrouteservice",
                fetched_at=FETCHED,
            )
        ],
    )
    access = ingest.summarise_access(ACCESS_RESPONSE, FETCHED)
    enriched = ingest.enrich(cache, access)
    assert enriched.access_tags == access
    assert enriched.routes == cache.routes and enriched.nearby == cache.nearby


def test_cache_without_access_tags_is_written_without_the_key(tmp_path: Path) -> None:
    from haven.location import write_cache

    path = write_cache(LocationCacheFile(property_id="p", origin=ORIGIN), tmp_path)
    assert "access_tags" not in json.loads(path.read_text("utf-8"))


def test_committed_caches_have_access_tags() -> None:
    from haven.location import read_cache

    for prop in load_seed().list():
        cache = read_cache(ingest.cache_path(prop.id))
        assert cache.access_tags is not None, prop.id
        assert cache.access_tags.radius_m == ingest.ACCESS_RADIUS_M
