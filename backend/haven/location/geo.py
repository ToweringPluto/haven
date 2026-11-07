"""Small geodesy helpers."""

from math import asin, cos, radians, sin, sqrt

# IUGG mean Earth radius (R1), metres. Haversine on a sphere is accurate to ~0.5 %,
# which is plenty for "within N metres" checks over a city.
EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    p1, p2 = radians(lat1), radians(lat2)
    dlat = p2 - p1
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))
