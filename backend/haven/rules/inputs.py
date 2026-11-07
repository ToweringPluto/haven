"""Gather the location context the rules need for one property and renter."""

from haven.domain import Property, RenterProfile, Status
from haven.location import CachedProvider, LocationContext, PlaceKind, Point

RADIUS_M = 1500.0
STOP_KINDS = (PlaceKind.bus_stop, PlaceKind.tram_stop, PlaceKind.rail_station)


def location_for(
    provider: CachedProvider, prop: Property, profile: RenterProfile, radius_m: float = RADIUS_M
) -> LocationContext:
    """Nearby places plus routes to the renter's destinations and the nearest stops.

    Stops are looked up first so their routes (built by ``build_routes.py``) can be
    requested by coordinates; the walk-to-stop rule then finds them by stop name.
    """
    first = provider.context(prop, radius_m=radius_m)
    destinations = [
        Point(latitude=d.latitude, longitude=d.longitude, name=d.name) for d in profile.destinations
    ]
    for kind in STOP_KINDS:
        result = first.nearby_for(kind)
        if result is None or result.status is not Status.known or result.nearest is None:
            continue
        stop = result.nearest
        name = stop.name or f"nearest {kind.value.replace('_', ' ')}"
        destinations.append(Point(latitude=stop.latitude, longitude=stop.longitude, name=name))
    return provider.context(prop, radius_m=radius_m, destinations=destinations)
