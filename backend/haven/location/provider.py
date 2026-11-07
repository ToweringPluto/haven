"""Location providers: the ``LocationProvider`` protocol and the file-backed ``CachedProvider``.

The cache (``data/location_cache/<property_id>.json``, schema
:class:`~haven.location.models.LocationCacheFile`) is written by the ingest scripts
(``ingest_osm.py``, ``build_routes.py``) and only read here. Anything the cache can't
answer (no file, a kind that wasn't searched, a larger radius than was searched, a route
that wasn't built, a property without coordinates) comes back ``insufficient`` with a
note; it is never reported as "nothing nearby".
"""

import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from haven.config import LOCATION_CACHE_DIR
from haven.domain import Property, Status
from haven.location.geo import haversine_m
from haven.location.models import (
    LocationCacheFile,
    LocationContext,
    NearbyResult,
    PlaceKind,
    Point,
    RouteProfile,
    RouteResult,
)

# Two points closer than this are treated as the same location when matching a request
# against the cache. Cached distances are measured from the cached origin, so keep it small.
MATCH_TOLERANCE_M = 1.0

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class LocationCacheError(ValueError):
    """A location cache file exists but can't be read or doesn't match the schema."""


class LocationProvider(Protocol):
    def nearby(
        self, lat: float, lon: float, kinds: Iterable[PlaceKind], radius_m: float
    ) -> list[NearbyResult]:
        """One result per requested kind, in request order."""
        ...

    def route(self, origin: Point, destination: Point, profile: RouteProfile) -> RouteResult: ...


def insufficient_nearby(kind: PlaceKind, radius_m: float, note: str) -> NearbyResult:
    return NearbyResult(kind=kind, radius_m=radius_m, status=Status.insufficient, note=note)


def insufficient_route(
    origin: Point | None, destination: Point, profile: RouteProfile, note: str
) -> RouteResult:
    return RouteResult(
        profile=profile,
        origin=origin,
        destination=destination,
        status=Status.insufficient,
        note=note,
    )


def cache_path(property_id: str, directory: Path | None = None) -> Path:
    """Path of a property's cache file. Rejects ids that aren't safe file names."""
    if not _SAFE_ID.fullmatch(property_id):
        raise ValueError(f"property id {property_id!r} is not a safe cache file name")
    return (LOCATION_CACHE_DIR if directory is None else directory) / f"{property_id}.json"


def read_cache(path: Path) -> LocationCacheFile:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LocationCacheError(f"cannot read location cache {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LocationCacheError(f"invalid JSON in location cache {path}: {exc}") from exc
    try:
        cache = LocationCacheFile.model_validate(raw)
    except ValidationError as exc:
        raise LocationCacheError(f"location cache {path} does not match the schema: {exc}") from exc
    if cache.property_id != path.stem:
        raise LocationCacheError(
            f"location cache {path} is for property {cache.property_id!r}, not {path.stem!r}"
        )
    return cache


def write_cache(cache: LocationCacheFile, directory: Path | None = None) -> Path:
    """Write ``cache`` deterministically (2-space JSON, LF, trailing newline)."""
    path = cache_path(cache.property_id, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cache.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(text.encode("utf-8"))
    return path


def _same_point(a: Point, lat: float, lon: float) -> bool:
    return haversine_m(a.latitude, a.longitude, lat, lon) <= MATCH_TOLERANCE_M


def _nearby_from(cache: LocationCacheFile, kind: PlaceKind, radius_m: float) -> NearbyResult:
    entry = next((e for e in cache.nearby if e.kind is kind), None)
    if entry is None:
        return insufficient_nearby(kind, radius_m, f"no cached search for {kind.value} places")
    if radius_m > entry.radius_m:
        return insufficient_nearby(
            kind,
            radius_m,
            f"cached search for {kind.value} only covers {entry.radius_m:g} m, "
            f"not the requested {radius_m:g} m",
        )
    return NearbyResult(
        kind=kind,
        radius_m=radius_m,
        status=Status.known,
        places=sorted(
            (p for p in entry.places if p.distance_m <= radius_m), key=lambda p: p.distance_m
        ),
        source=entry.source,
        fetched_at=entry.fetched_at,
    )


def _route_from(
    cache: LocationCacheFile, origin: Point, destination: Point, profile: RouteProfile
) -> RouteResult:
    for r in cache.routes:
        if (
            r.profile is profile
            and r.origin is not None
            and _same_point(r.origin, origin.latitude, origin.longitude)
            and _same_point(r.destination, destination.latitude, destination.longitude)
        ):
            return r
    return insufficient_route(
        origin, destination, profile, f"no cached {profile.value} route to this destination"
    )


class CachedProvider:
    """Reads location data from ``data/location_cache/`` (or ``directory``). Never fetches."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = LOCATION_CACHE_DIR if directory is None else directory
        self._by_id: dict[str, LocationCacheFile] | None = None

    def _index(self) -> dict[str, LocationCacheFile]:
        if self._by_id is None:
            files = sorted(self.directory.glob("*.json")) if self.directory.is_dir() else []
            self._by_id = {}
            for path in files:
                cache = read_cache(path)
                self._by_id[cache.property_id] = cache
        return self._by_id

    def load(self, property_id: str) -> LocationCacheFile | None:
        """The cache file for ``property_id``, or ``None`` if there isn't one."""
        if not _SAFE_ID.fullmatch(property_id):
            return None
        return self._index().get(property_id)

    def _at(self, lat: float, lon: float) -> LocationCacheFile | None:
        return next((c for c in self._index().values() if _same_point(c.origin, lat, lon)), None)

    def nearby(
        self, lat: float, lon: float, kinds: Iterable[PlaceKind], radius_m: float
    ) -> list[NearbyResult]:
        cache = self._at(lat, lon)
        if cache is None:
            return [
                insufficient_nearby(k, radius_m, "no location data cached for this point")
                for k in kinds
            ]
        return [_nearby_from(cache, k, radius_m) for k in kinds]

    def route(self, origin: Point, destination: Point, profile: RouteProfile) -> RouteResult:
        cache = self._at(origin.latitude, origin.longitude)
        if cache is None:
            return insufficient_route(
                origin, destination, profile, "no location data cached for this point"
            )
        return _route_from(cache, origin, destination, profile)

    def context(
        self,
        prop: Property,
        *,
        kinds: Iterable[PlaceKind] = tuple(PlaceKind),
        radius_m: float,
        destinations: Sequence[Point] = (),
        profiles: Iterable[RouteProfile] = tuple(RouteProfile),
    ) -> LocationContext:
        """Location context for ``prop``, looked up by its id (not by coordinates)."""
        kinds, profiles = list(kinds), list(profiles)
        origin = (
            None
            if prop.latitude is None or prop.longitude is None
            else Point(latitude=prop.latitude, longitude=prop.longitude)
        )
        cache = self.load(prop.id)
        if origin is None:
            reason = "the property has no coordinates"
        elif cache is None:
            reason = "no location data cached for this property"
        elif not _same_point(cache.origin, origin.latitude, origin.longitude):
            reason = "cached location data is for different coordinates (stale cache)"
            cache = None
        else:
            reason = ""

        if origin is None or cache is None:
            nearby = [insufficient_nearby(k, radius_m, reason) for k in kinds]
            routes = [
                insufficient_route(origin, d, p, reason) for d in destinations for p in profiles
            ]
            return LocationContext(property_id=prop.id, origin=origin, nearby=nearby, routes=routes)

        return LocationContext(
            property_id=prop.id,
            origin=origin,
            nearby=[_nearby_from(cache, k, radius_m) for k in kinds],
            routes=[_route_from(cache, origin, d, p) for d in destinations for p in profiles],
        )
