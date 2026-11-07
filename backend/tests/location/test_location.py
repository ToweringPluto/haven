"""Location provider: models, cache format and the insufficient-not-empty rule."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from haven.config import LOCATION_CACHE_DIR, Settings
from haven.domain import Property, Status
from haven.location import (
    CachedProvider,
    LocationCacheError,
    LocationCacheFile,
    LocationProvider,
    NearbyCacheEntry,
    NearbyResult,
    Place,
    PlaceKind,
    Point,
    RouteProfile,
    RouteResult,
    cache_path,
    haversine_m,
    read_cache,
    write_cache,
)
from haven.store import load_seed

FETCHED = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
OSM = "OpenStreetMap (Overpass API)"
ORIGIN = Point(latitude=55.9700, longitude=-3.1700)
WAVERLEY = Point(latitude=55.9521, longitude=-3.1890, name="Edinburgh Waverley")
ELSEWHERE = Point(latitude=55.9300, longitude=-3.2100, name="Somewhere else")


def _place(kind: PlaceKind, distance_m: float, name: str = "Stop") -> Place:
    return Place(
        kind=kind,
        name=name,
        latitude=55.97,
        longitude=-3.17,
        distance_m=distance_m,
        source=OSM,
        source_ref="osm:node/1",
        fetched_at=FETCHED,
    )


def _cache(property_id: str = "prop-a", origin: Point = ORIGIN) -> LocationCacheFile:
    return LocationCacheFile(
        property_id=property_id,
        origin=origin,
        nearby=[
            NearbyCacheEntry(
                kind=PlaceKind.bus_stop,
                radius_m=1500,
                source=OSM,
                fetched_at=FETCHED,
                places=[
                    _place(PlaceKind.bus_stop, 900, "Far"),
                    _place(PlaceKind.bus_stop, 120, "Near"),
                ],
            ),
            NearbyCacheEntry(
                kind=PlaceKind.pharmacy, radius_m=1500, source=OSM, fetched_at=FETCHED
            ),
        ],
        routes=[
            RouteResult(
                profile=RouteProfile.wheelchair,
                origin=origin,
                destination=WAVERLEY,
                status=Status.known,
                distance_m=2400,
                duration_s=1900,
                data_completeness=0.4,
                source="openrouteservice",
                fetched_at=FETCHED,
            ),
            RouteResult(
                profile=RouteProfile.foot_walking,
                origin=origin,
                destination=WAVERLEY,
                status=Status.estimated,
                distance_m=3000,
                source="straight line x 1.3",
                fetched_at=FETCHED,
                note="routing unavailable",
            ),
        ],
    )


def _property(
    property_id: str = "prop-a", lat: float | None = 55.97, lon: float | None = -3.17
) -> Property:
    seed = load_seed().list()[0]
    return seed.model_copy(update={"id": property_id, "latitude": lat, "longitude": lon})


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    write_cache(_cache(), tmp_path)
    return tmp_path


# --- models --------------------------------------------------------------------------


def test_haversine_known_distance() -> None:
    # One degree of latitude is ~111.2 km on the IUGG mean sphere.
    assert haversine_m(55.0, -3.0, 56.0, -3.0) == pytest.approx(111_195, rel=1e-3)
    assert haversine_m(55.97, -3.17, 55.97, -3.17) == 0


def test_place_requires_aware_fetched_at() -> None:
    with pytest.raises(ValidationError):
        Place(
            kind=PlaceKind.school,
            latitude=55.9,
            longitude=-3.1,
            distance_m=10,
            source=OSM,
            fetched_at=datetime(2026, 11, 7, 12, 0),
        )


def test_every_cached_item_carries_source_and_fetched_at() -> None:
    dumped = _cache().model_dump(mode="json")
    for entry in dumped["nearby"]:
        assert entry["source"] and entry["fetched_at"]
        for place in entry["places"]:
            assert place["source"] and place["fetched_at"]
    for route in dumped["routes"]:
        assert route["source"] and route["fetched_at"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": Status.insufficient},  # no note
        {"status": Status.insufficient, "note": "x", "places": [_place(PlaceKind.bus_stop, 5)]},
        {"status": Status.known},  # no source / fetched_at
        {
            "status": Status.known,
            "source": OSM,
            "fetched_at": FETCHED,
            "places": [_place(PlaceKind.school, 5)],  # wrong kind
        },
        {
            "status": Status.known,
            "source": OSM,
            "fetched_at": FETCHED,
            "places": [_place(PlaceKind.bus_stop, 2000)],  # outside radius
        },
    ],
)
def test_nearby_result_validation(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        NearbyResult(kind=PlaceKind.bus_stop, radius_m=500, **kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": Status.insufficient},  # no note
        {"status": Status.insufficient, "note": "x", "distance_m": 10},
        {"status": Status.known, "source": "ors", "fetched_at": FETCHED},  # no distance
        {"status": Status.known, "distance_m": 10},  # no source
        {"status": Status.estimated, "distance_m": 10, "source": "x", "fetched_at": FETCHED},
        {"status": Status.uncertain, "distance_m": 10, "source": "x", "fetched_at": FETCHED},
        {
            "status": Status.known,
            "distance_m": 10,
            "source": "ors",
            "fetched_at": FETCHED,
            "data_completeness": 1.5,
        },
    ],
)
def test_route_result_validation(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RouteResult(profile=RouteProfile.wheelchair, origin=ORIGIN, destination=WAVERLEY, **kwargs)


def test_known_route_needs_origin() -> None:
    with pytest.raises(ValidationError):
        RouteResult(
            profile=RouteProfile.wheelchair,
            origin=None,
            destination=WAVERLEY,
            status=Status.known,
            distance_m=10,
            source="ors",
            fetched_at=FETCHED,
        )


def test_cache_file_rejects_duplicates_and_insufficient_routes() -> None:
    entry = NearbyCacheEntry(kind=PlaceKind.school, radius_m=100, source=OSM, fetched_at=FETCHED)
    with pytest.raises(ValidationError):
        LocationCacheFile(property_id="p", origin=ORIGIN, nearby=[entry, entry])
    bad_route = RouteResult(
        profile=RouteProfile.wheelchair,
        origin=ORIGIN,
        destination=WAVERLEY,
        status=Status.insufficient,
        note="no route",
    )
    with pytest.raises(ValidationError):
        LocationCacheFile(property_id="p", origin=ORIGIN, routes=[bad_route])
    with pytest.raises(ValidationError):
        NearbyCacheEntry(
            kind=PlaceKind.school,
            radius_m=100,
            source=OSM,
            fetched_at=FETCHED,
            places=[_place(PlaceKind.school, 150)],
        )


# --- cache files ---------------------------------------------------------------------


def test_cache_round_trip_is_deterministic(tmp_path: Path) -> None:
    path = write_cache(_cache(), tmp_path)
    assert path == tmp_path / "prop-a.json"
    first = path.read_bytes()
    assert b"\r\n" not in first and first.endswith(b"\n")
    assert read_cache(path) == _cache()
    write_cache(read_cache(path), tmp_path)
    assert path.read_bytes() == first
    assert json.loads(first)["schema_version"] == 1


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", "", ".hidden", "a b"])
def test_cache_path_rejects_unsafe_ids(bad_id: str) -> None:
    with pytest.raises(ValueError):
        cache_path(bad_id)
    assert CachedProvider(Path("unused")).load(bad_id) is None


def test_default_cache_dir() -> None:
    assert cache_path("x") == LOCATION_CACHE_DIR / "x.json"
    assert Settings().location_cache_dir == LOCATION_CACHE_DIR
    assert CachedProvider().directory == LOCATION_CACHE_DIR


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("{not json", "invalid JSON"),
        ('{"schema_version": 2}', "does not match"),
    ],
)
def test_broken_cache_file_raises(tmp_path: Path, content: str, match: str) -> None:
    (tmp_path / "prop-a.json").write_text(content, encoding="utf-8")
    with pytest.raises(LocationCacheError, match=match):
        CachedProvider(tmp_path).load("prop-a")


def test_cache_file_must_match_its_name(tmp_path: Path) -> None:
    write_cache(_cache("prop-b"), tmp_path)
    (tmp_path / "prop-b.json").rename(tmp_path / "prop-a.json")
    with pytest.raises(LocationCacheError, match="is for property"):
        read_cache(tmp_path / "prop-a.json")


def test_unreadable_cache_raises(tmp_path: Path) -> None:
    with pytest.raises(LocationCacheError, match="cannot read"):
        read_cache(tmp_path / "missing.json")


def test_committed_cache_files_are_valid() -> None:
    # Whatever the ingest scripts have written so far must load.
    provider = CachedProvider()
    for path in sorted(LOCATION_CACHE_DIR.glob("*.json")):
        assert provider.load(path.stem) is not None


# --- provider: nearby ----------------------------------------------------------------


def test_cached_provider_satisfies_protocol(cache_dir: Path) -> None:
    provider: LocationProvider = CachedProvider(cache_dir)
    assert provider.nearby(55.97, -3.17, [PlaceKind.bus_stop], 500)[0].status is Status.known


def test_nearby_filters_by_radius_and_sorts(cache_dir: Path) -> None:
    [result] = CachedProvider(cache_dir).nearby(55.97, -3.17, [PlaceKind.bus_stop], 1000)
    assert result.status is Status.known
    assert [p.name for p in result.places] == ["Near", "Far"]
    assert result.nearest is not None and result.nearest.name == "Near"
    assert result.source == OSM and result.fetched_at == FETCHED
    [small] = CachedProvider(cache_dir).nearby(55.97, -3.17, [PlaceKind.bus_stop], 500)
    assert [p.name for p in small.places] == ["Near"]


def test_searched_but_none_found_is_known_and_empty(cache_dir: Path) -> None:
    [result] = CachedProvider(cache_dir).nearby(55.97, -3.17, [PlaceKind.pharmacy], 1500)
    assert result.status is Status.known
    assert result.places == [] and result.nearest is None


def test_unsearched_kind_is_insufficient(cache_dir: Path) -> None:
    [result] = CachedProvider(cache_dir).nearby(55.97, -3.17, [PlaceKind.tram_stop], 500)
    assert result.status is Status.insufficient
    assert result.places == []
    assert result.note and "tram_stop" in result.note


def test_radius_beyond_cached_search_is_insufficient(cache_dir: Path) -> None:
    [result] = CachedProvider(cache_dir).nearby(55.97, -3.17, [PlaceKind.bus_stop], 2000)
    assert result.status is Status.insufficient
    assert result.note and "1500" in result.note


def test_uncached_point_is_insufficient(cache_dir: Path) -> None:
    results = CachedProvider(cache_dir).nearby(
        55.90, -3.10, [PlaceKind.bus_stop, PlaceKind.school], 500
    )
    assert [r.kind for r in results] == [PlaceKind.bus_stop, PlaceKind.school]
    assert all(r.status is Status.insufficient and r.places == [] for r in results)


def test_empty_or_missing_cache_dir_is_insufficient(tmp_path: Path) -> None:
    for directory in (tmp_path, tmp_path / "does-not-exist"):
        [result] = CachedProvider(directory).nearby(55.97, -3.17, [PlaceKind.bus_stop], 500)
        assert result.status is Status.insufficient


# --- provider: routes ----------------------------------------------------------------


def test_cached_routes_are_returned_with_status(cache_dir: Path) -> None:
    provider = CachedProvider(cache_dir)
    wheelchair = provider.route(ORIGIN, WAVERLEY, RouteProfile.wheelchair)
    assert wheelchair.status is Status.known and wheelchair.distance_m == 2400
    walking = provider.route(ORIGIN, WAVERLEY, RouteProfile.foot_walking)
    assert walking.status is Status.estimated and walking.note == "routing unavailable"


def test_missing_route_is_insufficient(cache_dir: Path) -> None:
    provider = CachedProvider(cache_dir)
    result = provider.route(ORIGIN, ELSEWHERE, RouteProfile.wheelchair)
    assert result.status is Status.insufficient
    assert result.distance_m is None and result.note
    far_origin = Point(latitude=55.90, longitude=-3.10)
    assert provider.route(far_origin, WAVERLEY, RouteProfile.wheelchair).status is (
        Status.insufficient
    )


# --- provider: context ---------------------------------------------------------------


def test_context_from_cache(cache_dir: Path) -> None:
    ctx = CachedProvider(cache_dir).context(
        _property(), radius_m=1000, destinations=[WAVERLEY, ELSEWHERE]
    )
    assert ctx.property_id == "prop-a" and ctx.origin is not None
    assert [n.kind for n in ctx.nearby] == list(PlaceKind)
    bus = ctx.nearby_for(PlaceKind.bus_stop)
    assert bus is not None and bus.status is Status.known and len(bus.places) == 2
    tram = ctx.nearby_for(PlaceKind.tram_stop)
    assert tram is not None and tram.status is Status.insufficient
    assert len(ctx.routes) == 2 * len(RouteProfile)
    route = ctx.route_to("Edinburgh Waverley", RouteProfile.wheelchair)
    assert route is not None and route.status is Status.known
    other = ctx.route_to("Somewhere else", RouteProfile.wheelchair)
    assert other is not None and other.status is Status.insufficient
    assert ctx.route_to("Nowhere", RouteProfile.wheelchair) is None


@pytest.mark.parametrize(
    ("prop_kwargs", "reason"),
    [
        ({"property_id": "prop-uncached"}, "no location data cached"),
        ({"lat": None, "lon": None}, "no coordinates"),
        ({"lat": 55.90, "lon": -3.10}, "stale cache"),
    ],
)
def test_context_without_usable_cache_is_insufficient(
    cache_dir: Path, prop_kwargs: dict[str, Any], reason: str
) -> None:
    ctx = CachedProvider(cache_dir).context(
        _property(**prop_kwargs),
        kinds=[PlaceKind.bus_stop, PlaceKind.gp_surgery],
        radius_m=500,
        destinations=[WAVERLEY],
        profiles=[RouteProfile.wheelchair],
    )
    assert len(ctx.nearby) == 2 and len(ctx.routes) == 1
    for item in [*ctx.nearby, *ctx.routes]:
        assert item.status is Status.insufficient
        assert item.note and reason in item.note
    assert all(n.places == [] for n in ctx.nearby)
    assert all(r.distance_m is None for r in ctx.routes)


def test_seed_property_without_cache_is_insufficient(tmp_path: Path) -> None:
    prop = load_seed().list()[0]
    ctx = CachedProvider(tmp_path).context(prop, radius_m=500)
    assert ctx.nearby and all(n.status is Status.insufficient for n in ctx.nearby)
