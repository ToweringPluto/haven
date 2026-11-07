"""Add walking and wheelchair routes to ``data/location_cache/`` for every seed property.

For each seed property, routes go to the destination set (University of Edinburgh Central
Area, Edinburgh Waverley, Royal Infirmary of Edinburgh) and to the nearest bus stop, tram
stop and rail station in its cache (from ``ingest_osm.py``), for both OpenRouteService
profiles ``foot-walking`` and ``wheelchair``.

Each route records distance, duration and **data completeness**: the share of the route's
length with a known surface type, from ORS ``extra_info=surface``. ORS doesn't report kerb or
incline tags, so this is surface data coverage only, and the route note says so.

Without an ORS key (``ORS_API_KEY`` in the environment or ``backend/.env``), or when ORS
can't route a pair, the route falls back to straight-line distance x 1.3 with status
``estimated``, no duration, and the note "routing unavailable". Raw ORS responses are kept in
``data/raw/ors/<property_id>/`` so the cache can be rebuilt offline.

Usage (from ``backend/``)::

    uv run python scripts/build_routes.py            # fetch missing routes, write the cache
    uv run python scripts/build_routes.py --offline  # raw files only (fallback for the rest)
    uv run python scripts/build_routes.py --check    # validate the cache (no network)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from haven.config import LOCATION_CACHE_DIR, REPO_ROOT
from haven.domain import Property, Status
from haven.location import (
    LocationCacheFile,
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

USER_AGENT = "haven-prototype"
ORS_URL = "https://api.openrouteservice.org/v2/directions/{profile}/json"
ORS_SOURCE = "openrouteservice (OpenStreetMap data)"
ORS_PROFILES = {RouteProfile.foot_walking: "foot-walking", RouteProfile.wheelchair: "wheelchair"}
RAW_DIR = REPO_ROOT / "data" / "raw" / "ors"
ENV_FILE = REPO_ROOT / "backend" / ".env"
PAUSE_S = 1.6  # ORS free tier: 40 directions requests a minute
DETOUR_FACTOR = 1.3
FALLBACK_SOURCE = "Haven straight-line estimate"
SURFACE_UNKNOWN = 0  # ORS surface extra_info value for "Unknown"

# Destination coordinates: the two persona destinations use the coordinates in
# contracts/examples (so profile destinations match cached routes); Waverley uses the OSM
# railway=station "Edinburgh Waverley" point as cached by ingest_osm.py (seed-prop-old-town).
DESTINATIONS = [
    Point(latitude=55.9445, longitude=-3.1892, name="University of Edinburgh Central Area"),
    Point(latitude=55.9519018, longitude=-3.1904199, name="Edinburgh Waverley"),
    Point(latitude=55.9216, longitude=-3.1347, name="Royal Infirmary of Edinburgh"),
]
STOP_KINDS = (PlaceKind.bus_stop, PlaceKind.tram_stop, PlaceKind.rail_station)


class RoutingError(Exception):
    """ORS couldn't produce a route for this pair (or returned something unusable)."""


def ors_key() -> str | None:
    key = os.environ.get("ORS_API_KEY")
    if key:
        return key.strip()
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ORS_API_KEY" and value.strip():
                return value.strip().strip("'\"")
    return None


def destinations_for(cache: LocationCacheFile) -> list[Point]:
    """The fixed destination set plus the nearest stop of each kind in the cache."""
    points = list(DESTINATIONS)
    for kind in STOP_KINDS:
        entry = next((e for e in cache.nearby if e.kind is kind), None)
        if entry is None or not entry.places:
            continue
        stop = min(entry.places, key=lambda p: p.distance_m)
        if any(_same(stop.latitude, stop.longitude, p) for p in points):
            continue  # e.g. the nearest station is Edinburgh Waverley itself
        name = stop.name or f"nearest {kind.value.replace('_', ' ')}"
        points.append(Point(latitude=stop.latitude, longitude=stop.longitude, name=name))
    return points


def _same(lat: float, lon: float, point: Point) -> bool:
    return haversine_m(lat, lon, point.latitude, point.longitude) <= 1.0


def parse_ors(
    payload: Mapping[str, Any],
    origin: Point,
    destination: Point,
    profile: RouteProfile,
    fetched_at: datetime,
) -> RouteResult:
    routes = payload.get("routes")
    if not routes:
        error = payload.get("error")
        raise RoutingError(f"no route returned: {error}" if error else "no route returned")
    route = routes[0]
    summary = route.get("summary") or {}
    distance = summary.get("distance")
    if distance is None:
        raise RoutingError("route has no distance")
    completeness = surface_completeness(route.get("extras") or {})
    note = (
        "Data completeness = share of the route's length with a known surface type (ORS "
        "surface data); kerb heights and inclines aren't reported, so check them in person."
    )
    if completeness is None:
        note = "ORS returned no surface data for this route, so data completeness is unknown."
    return RouteResult(
        profile=profile,
        origin=origin,
        destination=destination,
        status=Status.known,
        distance_m=round(float(distance), 1),
        duration_s=round(float(summary.get("duration") or 0.0), 1),
        data_completeness=completeness,
        source=ORS_SOURCE,
        fetched_at=fetched_at,
        note=note,
    )


def surface_completeness(extras: Mapping[str, Any]) -> float | None:
    """Share of route length whose surface isn't 'Unknown', from ORS ``extras.surface``."""
    surface = extras.get("surface")
    if not isinstance(surface, Mapping) or not surface.get("summary"):
        return None
    unknown = sum(
        float(item.get("amount") or 0.0)
        for item in surface["summary"]
        if item.get("value") == SURFACE_UNKNOWN
    )
    return round(max(0.0, min(1.0, 1 - unknown / 100)), 3)


def fallback_route(
    origin: Point, destination: Point, profile: RouteProfile, reason: str, at: datetime
) -> RouteResult:
    straight = haversine_m(
        origin.latitude, origin.longitude, destination.latitude, destination.longitude
    )
    return RouteResult(
        profile=profile,
        origin=origin,
        destination=destination,
        status=Status.estimated,
        distance_m=round(straight * DETOUR_FACTOR, 1),
        duration_s=None,
        data_completeness=None,
        source=FALLBACK_SOURCE,
        fetched_at=at,
        note=f"routing unavailable ({reason}): straight-line distance x {DETOUR_FACTOR}; "
        "no duration or accessibility data.",
    )


def raw_path(property_id: str, destination: Point, profile: RouteProfile) -> Path:
    # Names aren't unique (Haymarket is a tram stop and a rail station), so add coordinates.
    slug = re.sub(r"[^a-z0-9]+", "-", (destination.name or "destination").lower()).strip("-")
    where = f"{destination.latitude:.5f}_{destination.longitude:.5f}"
    folder = cache_path(property_id, RAW_DIR).with_suffix("")
    return folder / f"{profile.value}__{slug}__{where}.json"


def fetch_ors(
    client: httpx.Client, key: str, origin: Point, destination: Point, profile: RouteProfile
) -> dict[str, Any]:
    response = client.post(
        ORS_URL.format(profile=ORS_PROFILES[profile]),
        headers={"Authorization": key},
        json={
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "extra_info": ["surface"],
        },
        timeout=60,
    )
    return {
        "url": str(response.request.url),
        "coordinates": [
            [origin.longitude, origin.latitude],
            [destination.longitude, destination.latitude],
        ],
        "status_code": response.status_code,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "response": response.json(),
    }


def route_for(
    prop: Property,
    origin: Point,
    destination: Point,
    profile: RouteProfile,
    fetch: Callable[[Point, Point, RouteProfile], dict[str, Any]] | None,
    now: datetime,
) -> RouteResult:
    path = raw_path(prop.id, destination, profile)
    raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    expected = [[origin.longitude, origin.latitude], [destination.longitude, destination.latitude]]
    if raw is not None and raw.get("coordinates") != expected:
        raw = None  # stale or legacy raw file: don't attribute it to these points
    if raw is not None:
        pass
    elif fetch is not None:
        raw = fetch(origin, destination, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw, indent=1) + "\n", encoding="utf-8")
    else:
        return fallback_route(origin, destination, profile, "no ORS key", now)
    fetched_at = datetime.fromisoformat(raw["fetched_at"])
    try:
        if raw.get("status_code", 200) != 200:
            raise RoutingError(f"ORS HTTP {raw['status_code']}")
        return parse_ors(raw["response"], origin, destination, profile, fetched_at)
    except RoutingError as exc:
        return fallback_route(origin, destination, profile, f"ORS: {exc}", fetched_at)


def build(props: list[Property], *, offline: bool, cache_dir: Path = LOCATION_CACHE_DIR) -> None:
    key = None if offline else ors_key()
    now = datetime.now(UTC).replace(microsecond=0)
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:

        def fetch(origin: Point, destination: Point, profile: RouteProfile) -> dict[str, Any]:
            time.sleep(PAUSE_S)
            assert key is not None
            return fetch_ors(client, key, origin, destination, profile)

        for prop in props:
            cache = read_cache(cache_path(prop.id, cache_dir))
            origin = cache.origin
            routes = [
                route_for(prop, origin, dest, profile, fetch if key else None, now)
                for dest in destinations_for(cache)
                for profile in RouteProfile
            ]
            write_cache(cache.model_copy(update={"routes": routes}), cache_dir)
            known = sum(r.status is Status.known for r in routes)
            print(f"{prop.id}: {known}/{len(routes)} routed, {len(routes) - known} estimated")


def check(props: list[Property], cache_dir: Path = LOCATION_CACHE_DIR) -> list[str]:
    problems = []
    for prop in props:
        path = cache_path(prop.id, cache_dir)
        if not path.is_file():
            problems.append(f"{prop.id}: no cache file (run ingest_osm.py first)")
            continue
        cache = read_cache(path)
        have = {(r.destination.name, r.profile) for r in cache.routes}
        for dest in destinations_for(cache):
            for profile in RouteProfile:
                if (dest.name, profile) not in have:
                    problems.append(f"{prop.id}: no {profile.value} route to {dest.name}")
        for r in cache.routes:
            if r.status is Status.estimated and "routing unavailable" not in (r.note or ""):
                problems.append(f"{prop.id}: estimated route without 'routing unavailable' note")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate the cache (no network)")
    mode.add_argument("--offline", action="store_true", help="no network; fallback if no raw")
    args = parser.parse_args(argv)
    props = load_seed().list()
    if args.check:
        problems = check(props)
        for problem in problems:
            print(problem, file=sys.stderr)
        if not problems:
            print(f"routes are present for {len(props)} seed properties")
        return 1 if problems else 0
    try:
        build(props, offline=args.offline)
    except httpx.HTTPError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
