"""Route building: ORS response parsing, surface completeness and the fallback."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from haven.domain import Status
from haven.location import (
    LocationCacheFile,
    NearbyCacheEntry,
    Place,
    PlaceKind,
    Point,
    RouteProfile,
)
from scripts import build_routes as br

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "osm" / "ors_wheelchair_sample.json"
AT = datetime(2026, 11, 7, 12, tzinfo=UTC)
ORIGIN = Point(latitude=55.95, longitude=-3.19)
DEST = Point(latitude=55.9445, longitude=-3.1892, name="University of Edinburgh Central Area")


def test_parse_ors_sample() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    route = br.parse_ors(payload, ORIGIN, DEST, RouteProfile.wheelchair, AT)
    assert route.status is Status.known
    assert (route.distance_m, route.duration_s) == (1234.5, 987.6)
    assert route.data_completeness == pytest.approx(0.7695, abs=0.001)
    assert "kerb" in (route.note or "") and route.source == br.ORS_SOURCE


def test_surface_completeness_edge_cases() -> None:
    assert br.surface_completeness({}) is None
    assert br.surface_completeness({"surface": {"summary": []}}) is None
    assert br.surface_completeness({"surface": {"summary": [{"value": 1, "amount": 100}]}}) == 1.0
    payload = {"routes": [{"summary": {"distance": 10, "duration": 5}}]}
    route = br.parse_ors(payload, ORIGIN, DEST, RouteProfile.foot_walking, AT)
    assert route.data_completeness is None and "no surface data" in (route.note or "")


def test_parse_ors_errors() -> None:
    with pytest.raises(br.RoutingError, match="no route"):
        br.parse_ors({"error": {"code": 2009}}, ORIGIN, DEST, RouteProfile.wheelchair, AT)
    with pytest.raises(br.RoutingError, match="distance"):
        br.parse_ors({"routes": [{"summary": {}}]}, ORIGIN, DEST, RouteProfile.wheelchair, AT)


def test_fallback_is_estimated_and_labelled() -> None:
    route = br.fallback_route(ORIGIN, DEST, RouteProfile.wheelchair, "no ORS key", AT)
    assert route.status is Status.estimated
    assert route.duration_s is None and route.data_completeness is None
    assert "routing unavailable" in (route.note or "")
    straight = br.haversine_m(ORIGIN.latitude, ORIGIN.longitude, DEST.latitude, DEST.longitude)
    assert route.distance_m == pytest.approx(straight * 1.3, abs=0.1)


def _cache() -> LocationCacheFile:
    stop = Place(
        kind=PlaceKind.bus_stop,
        name="Stop A",
        latitude=55.951,
        longitude=-3.19,
        distance_m=111.0,
        source="OSM",
        fetched_at=AT,
    )
    entries = [
        NearbyCacheEntry(
            kind=PlaceKind.bus_stop, radius_m=1500, source="OSM", fetched_at=AT, places=[stop]
        ),
        NearbyCacheEntry(kind=PlaceKind.tram_stop, radius_m=1500, source="OSM", fetched_at=AT),
    ]
    return LocationCacheFile(property_id="seed-prop-test", origin=ORIGIN, nearby=entries)


def test_destinations_include_nearest_stops() -> None:
    names = [d.name for d in br.destinations_for(_cache())]
    assert names == [d.name for d in br.DESTINATIONS] + ["Stop A"]


def test_build_offline_and_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haven.location import write_cache
    from haven.store import load_seed

    monkeypatch.setattr(br, "RAW_DIR", tmp_path / "raw")
    prop = load_seed().list()[0]
    cache = _cache().model_copy(
        update={
            "property_id": prop.id,
            "origin": Point(latitude=prop.latitude or 0, longitude=prop.longitude or 0),
        }
    )
    write_cache(cache, tmp_path)
    assert br.check([prop], tmp_path)  # no routes yet
    br.build([prop], offline=True, cache_dir=tmp_path)
    assert br.check([prop], tmp_path) == []
    routes = br.read_cache(br.cache_path(prop.id, tmp_path)).routes
    assert len(routes) == 4 * 2 and all(r.status is Status.estimated for r in routes)


def test_raw_path_is_safe() -> None:
    path = br.raw_path("seed-prop-leith", DEST, RouteProfile.wheelchair)
    assert path.name == "wheelchair__university-of-edinburgh-central-area__55.94450_-3.18920.json"
    assert path.parent.name == "seed-prop-leith"
