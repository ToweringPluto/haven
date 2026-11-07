"""location_for: requests routes to the renter's destinations and the nearest stops."""

from datetime import UTC, datetime
from pathlib import Path

from haven.domain import RenterProfile
from haven.location import (
    CachedProvider,
    LocationCacheFile,
    NearbyCacheEntry,
    Place,
    PlaceKind,
    Point,
    RouteProfile,
    RouteResult,
    write_cache,
)
from haven.rules import location_for
from haven.store import load_seed

AT = datetime(2026, 11, 7, 12, tzinfo=UTC)


def test_location_for_includes_stop_and_destination_routes(tmp_path: Path) -> None:
    prop = load_seed().list()[0]
    assert prop.latitude is not None and prop.longitude is not None
    origin = Point(latitude=prop.latitude, longitude=prop.longitude)
    stop = Place(
        kind=PlaceKind.bus_stop,
        name="Stop A",
        latitude=prop.latitude + 0.001,
        longitude=prop.longitude,
        distance_m=111.0,
        source="OSM",
        fetched_at=AT,
    )
    stop_point = Point(latitude=stop.latitude, longitude=stop.longitude, name="Stop A")
    uni = Point(latitude=55.9445, longitude=-3.1892, name="Uni")
    routes = [
        RouteResult(
            profile=RouteProfile.foot_walking,
            origin=origin,
            destination=dest,
            status="known",
            distance_m=150,
            duration_s=120,
            source="ors",
            fetched_at=AT,
        )
        for dest in (stop_point, uni)
    ]
    nearby = [
        NearbyCacheEntry(
            kind=PlaceKind.bus_stop, radius_m=1500, source="OSM", fetched_at=AT, places=[stop]
        ),
        NearbyCacheEntry(kind=PlaceKind.tram_stop, radius_m=1500, source="OSM", fetched_at=AT),
    ]
    write_cache(
        LocationCacheFile(property_id=prop.id, origin=origin, nearby=nearby, routes=routes),
        tmp_path,
    )
    profile = RenterProfile.model_validate(
        {
            "id": "r",
            "label": "R",
            "destinations": [{"name": "Uni", "latitude": 55.9445, "longitude": -3.1892}],
        }
    )
    ctx = location_for(CachedProvider(tmp_path), prop, profile)
    assert ctx.route_to("Stop A", RouteProfile.foot_walking).status == "known"
    assert ctx.route_to("Uni", RouteProfile.foot_walking).status == "known"
    assert ctx.route_to("Uni", RouteProfile.wheelchair).status == "insufficient"
