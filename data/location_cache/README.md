# Location cache

One JSON file per property, `<property_id>.json`, read by `haven.location.CachedProvider`.
Files are written by the ingest scripts (`backend/scripts/ingest_osm.py` for nearby places and,
with `--enrich`, access tags; `backend/scripts/build_routes.py` for routes) through `haven.location.write_cache`; never
edit them by hand. The schema is `haven.location.LocationCacheFile`:

```json
{
  "schema_version": 1,
  "property_id": "seed-prop-leith",
  "origin": {"latitude": 55.97, "longitude": -3.17, "name": null},
  "nearby": [
    {
      "kind": "bus_stop",
      "radius_m": 1500,
      "source": "OpenStreetMap (Overpass API)",
      "fetched_at": "2026-11-07T12:00:00Z",
      "places": [
        {"kind": "bus_stop", "name": "...", "latitude": 55.97, "longitude": -3.17,
         "distance_m": 120.5, "source": "OpenStreetMap (Overpass API)",
         "source_ref": "osm:node/123", "fetched_at": "2026-11-07T12:00:00Z"}
      ]
    }
  ],
  "routes": [
    {
      "profile": "wheelchair",
      "origin": {"latitude": 55.97, "longitude": -3.17, "name": null},
      "destination": {"latitude": 55.95, "longitude": -3.19, "name": "Edinburgh Waverley"},
      "status": "known",
      "distance_m": 2400, "duration_s": 1900, "data_completeness": 0.4,
      "source": "openrouteservice", "fetched_at": "2026-11-07T12:00:00Z", "note": null
    }
  ]
}
```

Files may also carry an optional `access_tags` block (from `ingest_osm.py --enrich`):
counts of OSM tags within `radius_m` (500 m) of the property: pedestrian-relevant `ways`, how
many of them have `surface`, `smoothness`, `incline` and `sidewalk` tags, `steps_ways`,
`crossings` (and how many have tactile paving), and `kerbs` by value (`lowered`, `flush`,
`raised`, `no`, `other`, `untagged`). It's a measure of how well the area is mapped, never a
verdict that a route is step-free.

Semantics:

- A `nearby` entry records everything of that kind found within `radius_m` of `origin`. An
  empty `places` list means "searched and found none". A kind that wasn't searched is left
  out, and lookups for it (or for a larger radius) come back `insufficient`.
- Every place and route carries `source` and `fetched_at` (timezone-aware ISO 8601).
- Routes have status `known` (routed) or `estimated` (fallback, with a `note` saying how).
  Unavailable routes are left out rather than cached as `insufficient`.
- No file for a property, or a file whose `origin` differs from the property's coordinates,
  means every location check for it is `insufficient`.
