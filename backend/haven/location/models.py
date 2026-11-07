"""Location data models: nearby places, routes, and the per-property cache file.

Every place and route carries its own ``source`` and ``fetched_at``. A lookup that the
data can't answer comes back with ``status == insufficient`` and a ``note`` saying why;
it is never turned into an empty-and-fine result. An empty ``places`` list with status
``known`` means "searched this radius and found none".
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from haven.domain import Status

CACHE_SCHEMA_VERSION: Literal[1] = 1


class PlaceKind(StrEnum):
    """Kinds of nearby amenity the location data covers."""

    bus_stop = "bus_stop"
    tram_stop = "tram_stop"
    rail_station = "rail_station"
    supermarket = "supermarket"
    pharmacy = "pharmacy"
    gp_surgery = "gp_surgery"
    school = "school"


class RouteProfile(StrEnum):
    """Routing profiles (mapped onto OpenRouteService ``foot-walking`` / ``wheelchair``)."""

    foot_walking = "foot_walking"
    wheelchair = "wheelchair"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Point(_Frozen):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    name: str | None = Field(default=None, description="Optional label, e.g. a destination.")


class Place(_Frozen):
    """One nearby amenity, with where and when it was read."""

    kind: PlaceKind
    name: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distance_m: float = Field(ge=0, description="Straight-line distance from the property.")
    source: str = Field(min_length=1, description="Named source, e.g. 'OpenStreetMap'.")
    source_ref: str | None = Field(
        default=None, description="Identifier in the source, e.g. 'osm:node/123'."
    )
    fetched_at: AwareDatetime


class NearbyResult(_Frozen):
    """Places of one kind within ``radius_m`` of a point."""

    kind: PlaceKind
    radius_m: float = Field(gt=0)
    status: Literal[Status.known, Status.insufficient]
    places: list[Place] = Field(default_factory=list)
    source: str | None = None
    fetched_at: AwareDatetime | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.status is Status.insufficient:
            if self.places:
                raise ValueError("an insufficient nearby result can't list places")
            if not self.note:
                raise ValueError("an insufficient nearby result needs a note saying why")
        elif self.source is None or self.fetched_at is None:
            raise ValueError("a known nearby result needs source and fetched_at")
        for p in self.places:
            if p.kind is not self.kind:
                raise ValueError(f"place of kind {p.kind} in a {self.kind} result")
            if p.distance_m > self.radius_m:
                raise ValueError("place lies outside the result's radius")
        return self

    @property
    def nearest(self) -> Place | None:
        return min(self.places, key=lambda p: p.distance_m, default=None)


class RouteResult(_Frozen):
    """A route between two points for one profile.

    ``status`` is ``known`` for a routed result, ``estimated`` for a fallback (e.g. a
    straight-line approximation) and ``insufficient`` when nothing is available.
    ``data_completeness`` is the share (0–1) of the route with accessibility tags
    (kerbs, incline, surface); ``None`` means it wasn't measured.
    """

    profile: RouteProfile
    origin: Point | None = Field(description="Null only when the start point is unknown.")
    destination: Point
    status: Literal[Status.known, Status.estimated, Status.insufficient]
    distance_m: float | None = Field(default=None, ge=0)
    duration_s: float | None = Field(default=None, ge=0)
    data_completeness: float | None = Field(default=None, ge=0, le=1)
    source: str | None = None
    fetched_at: AwareDatetime | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.status is Status.insufficient:
            if self.distance_m is not None or self.duration_s is not None:
                raise ValueError("an insufficient route can't carry a distance or duration")
            if not self.note:
                raise ValueError("an insufficient route needs a note saying why")
        else:
            if self.origin is None:
                raise ValueError("a known or estimated route needs an origin")
            if self.distance_m is None:
                raise ValueError("a known or estimated route needs distance_m")
            if self.source is None or self.fetched_at is None:
                raise ValueError("a known or estimated route needs source and fetched_at")
        if self.status is Status.estimated and not self.note:
            raise ValueError("an estimated route needs a note saying how it was estimated")
        return self


class LocationContext(_Frozen):
    """Everything the rules engine knows about a property's surroundings."""

    property_id: str = Field(min_length=1)
    origin: Point | None = Field(description="The property's coordinates, if known.")
    nearby: list[NearbyResult] = Field(default_factory=list)
    routes: list[RouteResult] = Field(default_factory=list)

    def nearby_for(self, kind: PlaceKind) -> NearbyResult | None:
        return next((n for n in self.nearby if n.kind is kind), None)

    def route_to(self, destination: str, profile: RouteProfile) -> RouteResult | None:
        return next(
            (r for r in self.routes if r.profile is profile and r.destination.name == destination),
            None,
        )


class NearbyCacheEntry(_Frozen):
    """Raw cached search for one kind: everything found within ``radius_m``."""

    kind: PlaceKind
    radius_m: float = Field(gt=0)
    source: str = Field(min_length=1)
    fetched_at: AwareDatetime
    places: list[Place] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Self:
        for p in self.places:
            if p.kind is not self.kind:
                raise ValueError(f"place of kind {p.kind} in a {self.kind} cache entry")
            if p.distance_m > self.radius_m:
                raise ValueError("cached place lies outside the searched radius")
        return self


class KerbCounts(_Frozen):
    """OSM kerb nodes (``kerb=*`` / ``barrier=kerb``) by their ``kerb`` value."""

    lowered: int = Field(default=0, ge=0)
    flush: int = Field(default=0, ge=0)
    raised: int = Field(default=0, ge=0)
    no: int = Field(default=0, ge=0, description="kerb=no (no kerb at all).")
    other: int = Field(default=0, ge=0, description="Any other value, e.g. 'rolled'.")
    untagged: int = Field(default=0, ge=0, description="barrier=kerb with no kerb=* value.")

    @property
    def total(self) -> int:
        return self.lowered + self.flush + self.raised + self.no + self.other + self.untagged


class AccessTagSummary(_Frozen):
    """How well the streets around a property are tagged for step-free access (OSM).

    Counts, not a verdict: a missing tag means unknown, never step-free or smooth. Ways are
    footways, paths, steps, pedestrian and ordinary streets within ``radius_m``.
    """

    radius_m: float = Field(gt=0)
    source: str = Field(min_length=1)
    fetched_at: AwareDatetime
    ways: int = Field(ge=0, description="Pedestrian-relevant ways within the radius.")
    ways_with_surface: int = Field(ge=0)
    ways_with_smoothness: int = Field(ge=0)
    ways_with_incline: int = Field(ge=0)
    ways_with_sidewalk: int = Field(ge=0)
    steps_ways: int = Field(ge=0, description="highway=steps ways (stairs on the street).")
    crossings: int = Field(ge=0, description="highway=crossing nodes.")
    crossings_with_tactile_paving: int = Field(ge=0)
    kerbs: KerbCounts

    @model_validator(mode="after")
    def _check(self) -> Self:
        for name in ("surface", "smoothness", "incline", "sidewalk"):
            if getattr(self, f"ways_with_{name}") > self.ways:
                raise ValueError(f"ways_with_{name} can't exceed ways")
        if self.crossings_with_tactile_paving > self.crossings:
            raise ValueError("crossings_with_tactile_paving can't exceed crossings")
        return self

    def coverage(self, tag: Literal["surface", "smoothness", "incline", "sidewalk"]) -> float:
        """Share of ways (0–1) carrying ``tag``; 0 when there are no ways."""
        count: int = getattr(self, f"ways_with_{tag}")
        return count / self.ways if self.ways else 0.0


class LocationCacheFile(_Frozen):
    """Schema of ``data/location_cache/<property_id>.json``."""

    schema_version: Literal[1] = CACHE_SCHEMA_VERSION
    property_id: str = Field(min_length=1)
    origin: Point
    nearby: list[NearbyCacheEntry] = Field(default_factory=list)
    routes: list[RouteResult] = Field(default_factory=list)
    access_tags: AccessTagSummary | None = Field(
        default=None,
        description="Kerb, incline, surface and crossing tags around the property (OSM). "
        "None means not fetched.",
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        kinds = [e.kind for e in self.nearby]
        if len(set(kinds)) != len(kinds):
            raise ValueError("duplicate nearby kind in cache file")
        if any(r.status is Status.insufficient for r in self.routes):
            raise ValueError("don't cache insufficient routes; leave them out instead")
        return self
