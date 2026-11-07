"""Fill ``data/location_cache/`` with nearby amenities for every seed property.

Two sources:

* **OpenStreetMap via the Overpass API**: one query per seed property (run one at a time,
  with a pause in between) for bus stops, tram stops, rail stations, supermarkets,
  pharmacies, GP surgeries and schools within ``RADIUS_M``. Raw responses are kept in
  ``data/raw/osm/<property_id>.json`` with the query and the time they were fetched, so the
  cache can be rebuilt offline.
* **Public Health Scotland GP practices** (second GP source): the quarterly "GP Practice
  Contact Details and List Sizes" CSV, filtered to NHS Lothian. It has postcodes but no
  coordinates, so each practice is placed at its **postcode centroid** (ONS Postcode Directory
  via postcodes.io). Raw files are in ``data/raw/gp/``.

Every place records its source and when it was fetched. Distances are straight-line from the
property; ways/relations use their Overpass ``center`` and are kept only if that centre lies
within the radius.

Usage (from ``backend/``)::

    uv run python scripts/ingest_osm.py            # fetch missing raw data, write the cache
    uv run python scripts/ingest_osm.py --refresh  # re-fetch everything, write the cache
    uv run python scripts/ingest_osm.py --offline  # rebuild from raw files only
    uv run python scripts/ingest_osm.py --check    # validate the cache (no network)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from haven.config import LOCATION_CACHE_DIR, REPO_ROOT, SEED_PATH
from haven.domain import Property
from haven.location import (
    MATCH_TOLERANCE_M,
    LocationCacheError,
    LocationCacheFile,
    NearbyCacheEntry,
    Place,
    PlaceKind,
    Point,
    cache_path,
    haversine_m,
    read_cache,
    write_cache,
)
from haven.store import load_seed

USER_AGENT = "haven-prototype"
RADIUS_M = 1500.0

OSM_RAW_DIR = REPO_ROOT / "data" / "raw" / "osm"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_SOURCE = "OpenStreetMap (Overpass API)"
PAUSE_S = 5.0
RETRY_STATUSES = {429, 502, 503, 504}
RETRY_WAIT_S = 30.0
MAX_ATTEMPTS = 3

GP_RAW_DIR = REPO_ROOT / "data" / "raw" / "gp"
GP_RELEASE = "October 2026"
GP_CSV_URL = (
    "https://www.opendata.nhs.scot/dataset/f23655c3-6e23-4103-a511-a80d998adb90/resource/"
    "ddfcdb81-860a-4851-8925-a094b63e1a00/download/practice_contact_details_20261001_opendata.csv"
)
GP_CSV = GP_RAW_DIR / "practice_contact_details_20261001_opendata.csv"
GP_MANIFEST = GP_RAW_DIR / "manifest.json"
NHS_LOTHIAN = "S08000024"
POSTCODES_URL = "https://api.postcodes.io/postcodes"
POSTCODE_BATCH = 100
GP_SOURCE = (
    f"Public Health Scotland, GP Practice Contact Details and List Sizes ({GP_RELEASE}); "
    "location is the practice postcode's centroid (ONS Postcode Directory via postcodes.io), "
    "so it is approximate"
)
GP_ENTRY_SOURCE = f"{OSM_SOURCE}; {GP_SOURCE}"

KIND_SELECTORS: dict[PlaceKind, list[str]] = {
    PlaceKind.bus_stop: ['node["highway"="bus_stop"]'],
    PlaceKind.tram_stop: ['node["railway"="tram_stop"]'],
    PlaceKind.rail_station: ['nwr["railway"~"^(station|halt)$"]'],
    PlaceKind.supermarket: ['nwr["shop"="supermarket"]'],
    PlaceKind.pharmacy: ['nwr["amenity"="pharmacy"]'],
    PlaceKind.gp_surgery: ['nwr["amenity"="doctors"]'],
    PlaceKind.school: ['nwr["amenity"="school"]'],
}
# railway=station values that aren't heavy rail (Edinburgh Trams, heritage lines, ...).
NOT_RAIL = {"light_rail", "subway", "tram", "miniature", "monorail", "funicular"}


class IngestError(Exception):
    """Raw data is missing or malformed, or a fetch failed."""


# --- Overpass ---------------------------------------------------------------------------


def build_query(lat: float, lon: float, radius_m: float = RADIUS_M) -> str:
    around = f"(around:{radius_m:g},{lat},{lon})"
    parts = [
        sel.replace("[", around + "[", 1)
        for selectors in KIND_SELECTORS.values()
        for sel in selectors
    ]
    body = "\n".join(f"  {p};" for p in parts)
    return f"[out:json][timeout:90];\n(\n{body}\n);\nout center tags;\n"


def classify(tags: Mapping[str, str]) -> PlaceKind | None:
    """Which kind an OSM element is (first match wins), or ``None`` if none applies."""
    if tags.get("highway") == "bus_stop":
        return PlaceKind.bus_stop
    railway = tags.get("railway")
    if railway == "tram_stop":
        return PlaceKind.tram_stop
    if railway in {"station", "halt"} and tags.get("station") not in NOT_RAIL:
        if tags.get("tram") == "yes" and tags.get("train") != "yes":
            return None
        return PlaceKind.rail_station
    if tags.get("shop") == "supermarket":
        return PlaceKind.supermarket
    amenity = tags.get("amenity")
    if amenity == "pharmacy":
        return PlaceKind.pharmacy
    if amenity == "doctors":
        return PlaceKind.gp_surgery
    if amenity == "school":
        return PlaceKind.school
    return None


def element_point(element: Mapping[str, Any]) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, Mapping) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def parse_overpass(
    response: Mapping[str, Any],
    origin: Point,
    fetched_at: datetime,
    radius_m: float = RADIUS_M,
) -> dict[PlaceKind, list[Place]]:
    """Places per kind from an Overpass JSON response (every kind present, maybe empty)."""
    elements = response.get("elements")
    if not isinstance(elements, list):
        raise IngestError("Overpass response has no 'elements' list")
    if response.get("remark"):
        # Overpass reports timeouts/out-of-memory as a remark with partial results.
        raise IngestError(f"Overpass returned a remark (partial result): {response['remark']}")
    found: dict[PlaceKind, dict[str, Place]] = {kind: {} for kind in PlaceKind}
    for element in elements:
        tags = element.get("tags") or {}
        kind = classify(tags)
        point = element_point(element)
        if kind is None or point is None:
            continue
        distance = haversine_m(origin.latitude, origin.longitude, *point)
        if distance > radius_m:
            continue
        ref = f"osm:{element['type']}/{element['id']}"
        found[kind][ref] = Place(
            kind=kind,
            name=tags.get("name") or None,
            latitude=point[0],
            longitude=point[1],
            distance_m=round(distance, 1),
            source=OSM_SOURCE,
            source_ref=ref,
            fetched_at=fetched_at,
        )
    return {kind: _sorted(places.values()) for kind, places in found.items()}


def _sorted(places: Iterable[Place]) -> list[Place]:
    return sorted(places, key=lambda p: (p.distance_m, p.source_ref or ""))


def osm_raw_path(property_id: str) -> Path:
    return OSM_RAW_DIR / cache_path(property_id, OSM_RAW_DIR).name


def _post_with_retries(
    client: httpx.Client, url: str, sleep: Callable[[float], None], **kwargs: Any
) -> httpx.Response:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.post(url, **kwargs)
        if response.status_code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
            response.raise_for_status()
            return response
        sleep(RETRY_WAIT_S * attempt)
    raise AssertionError("unreachable")


def fetch_overpass(
    client: httpx.Client, prop: Property, sleep: Callable[[float], None] = time.sleep
) -> dict[str, Any]:
    lat, lon = _coords(prop)
    query = build_query(lat, lon)
    response = _post_with_retries(client, OVERPASS_URL, sleep, data={"data": query}, timeout=180)
    return {
        "url": OVERPASS_URL,
        "query": query,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "response": response.json(),
    }


# --- GP practices (Public Health Scotland) ----------------------------------------------


@dataclass(frozen=True)
class GpPractice:
    code: str
    name: str
    postcode: str


def read_gp_practices(path: Path, health_board: str = NHS_LOTHIAN) -> list[GpPractice]:
    if not path.is_file():
        raise IngestError(f"{path} not found (run without --offline to download it)")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        needed = {"PracticeCode", "GPPracticeName", "Postcode", "HB"}
        missing = needed - set(reader.fieldnames or [])
        if missing:
            raise IngestError(f"{path.name} lacks columns: {', '.join(sorted(missing))}")
        practices = [
            GpPractice(
                code=row["PracticeCode"].strip(),
                name=row["GPPracticeName"].strip(),
                postcode=normalise_postcode(row["Postcode"]),
            )
            for row in reader
            if row["HB"].strip() == health_board
        ]
    if not practices:
        raise IngestError(f"no practices for health board {health_board} in {path.name}")
    return practices


def normalise_postcode(postcode: str) -> str:
    compact = "".join(postcode.split()).upper()
    return f"{compact[:-3]} {compact[-3:]}" if len(compact) > 3 else compact


def parse_postcodes(payload: Mapping[str, Any]) -> dict[str, tuple[float, float]]:
    """``{postcode: (lat, lon)}`` from a postcodes.io bulk lookup; unknown postcodes omitted."""
    coords: dict[str, tuple[float, float]] = {}
    for item in payload.get("result") or []:
        result = item.get("result")
        if not result or result.get("latitude") is None or result.get("longitude") is None:
            continue
        coords[normalise_postcode(item["query"])] = (
            float(result["latitude"]),
            float(result["longitude"]),
        )
    return coords


def gp_places(
    practices: Iterable[GpPractice],
    coords: Mapping[str, tuple[float, float]],
    origin: Point,
    fetched_at: datetime,
    radius_m: float = RADIUS_M,
) -> list[Place]:
    places = []
    for practice in practices:
        point = coords.get(practice.postcode)
        if point is None:
            continue
        distance = haversine_m(origin.latitude, origin.longitude, *point)
        if distance > radius_m:
            continue
        places.append(
            Place(
                kind=PlaceKind.gp_surgery,
                name=practice.name,
                latitude=point[0],
                longitude=point[1],
                distance_m=round(distance, 1),
                source=GP_SOURCE,
                source_ref=f"phs:gp_practice/{practice.code}",
                fetched_at=fetched_at,
            )
        )
    return places


def fetch_gp(client: httpx.Client) -> dict[str, Any]:
    """Download the PHS CSV (if missing) and geocode its Lothian postcodes."""
    GP_RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not GP_CSV.is_file():
        response = client.get(GP_CSV_URL, timeout=120, follow_redirects=True)
        response.raise_for_status()
        GP_CSV.write_bytes(response.content)
    csv_fetched_at = datetime.fromtimestamp(GP_CSV.stat().st_mtime, UTC)
    postcodes = sorted({p.postcode for p in read_gp_practices(GP_CSV)})
    results: list[dict[str, Any]] = []
    for start in range(0, len(postcodes), POSTCODE_BATCH):
        batch = postcodes[start : start + POSTCODE_BATCH]
        response = _post_with_retries(
            client, POSTCODES_URL, time.sleep, json={"postcodes": batch}, timeout=60
        )
        for item in response.json().get("result") or []:
            result = item.get("result") or {}
            results.append(
                {
                    "query": item.get("query"),
                    "result": (
                        {"latitude": result["latitude"], "longitude": result["longitude"]}
                        if result.get("latitude") is not None
                        else None
                    ),
                }
            )
    return {
        "csv_url": GP_CSV_URL,
        "csv_sha256": hashlib.sha256(GP_CSV.read_bytes()).hexdigest(),
        "csv_fetched_at": csv_fetched_at.isoformat(timespec="seconds"),
        "postcodes_url": POSTCODES_URL,
        "postcodes_fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "result": results,
    }


# --- cache assembly ---------------------------------------------------------------------


def _coords(prop: Property) -> tuple[float, float]:
    if prop.latitude is None or prop.longitude is None:
        raise IngestError(f"{prop.id} has no coordinates")
    return prop.latitude, prop.longitude


def build_cache(
    prop: Property,
    osm_raw: Mapping[str, Any],
    gp: list[Place],
    gp_fetched_at: datetime,
    existing: LocationCacheFile | None = None,
) -> LocationCacheFile:
    lat, lon = _coords(prop)
    origin = Point(latitude=lat, longitude=lon)
    osm_fetched_at = datetime.fromisoformat(osm_raw["fetched_at"])
    by_kind = parse_overpass(osm_raw["response"], origin, osm_fetched_at)
    nearby = []
    for kind in PlaceKind:
        places = by_kind[kind]
        source, fetched_at = OSM_SOURCE, osm_fetched_at
        if kind is PlaceKind.gp_surgery:
            # Both sources are kept: OSM mapping is patchy and PHS locations are approximate.
            places = _sorted([*places, *gp])
            source, fetched_at = GP_ENTRY_SOURCE, min(osm_fetched_at, gp_fetched_at)
        nearby.append(
            NearbyCacheEntry(
                kind=kind, radius_m=RADIUS_M, source=source, fetched_at=fetched_at, places=places
            )
        )
    routes = []
    if existing is not None and _close(existing.origin, origin):
        routes = list(existing.routes)  # keep routes built by build_routes.py
    return LocationCacheFile(property_id=prop.id, origin=origin, nearby=nearby, routes=routes)


def _close(a: Point, b: Point) -> bool:
    return haversine_m(a.latitude, a.longitude, b.latitude, b.longitude) <= MATCH_TOLERANCE_M


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise IngestError(f"{path} not found (run without --offline to fetch it)")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise IngestError(f"{path} is not a JSON object")
    return data


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_gp(manifest: Mapping[str, Any]) -> tuple[list[GpPractice], dict[str, tuple[float, float]]]:
    return read_gp_practices(GP_CSV), parse_postcodes(manifest)


def build_all(
    props: list[Property], cache_dir: Path = LOCATION_CACHE_DIR
) -> dict[str, LocationCacheFile]:
    """Cache files for every property, from the raw files on disk."""
    manifest = _read_json(GP_MANIFEST)
    practices, coords = load_gp(manifest)
    gp_fetched_at = datetime.fromisoformat(manifest["csv_fetched_at"])
    caches = {}
    for prop in props:
        lat, lon = _coords(prop)
        origin = Point(latitude=lat, longitude=lon)
        gp = gp_places(practices, coords, origin, gp_fetched_at)
        path = cache_path(prop.id, cache_dir)
        existing = read_cache(path) if path.is_file() else None
        caches[prop.id] = build_cache(
            prop, _read_json(osm_raw_path(prop.id)), gp, gp_fetched_at, existing
        )
    return caches


def fetch_missing(props: list[Property], refresh: bool) -> None:
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers) as client:
        if refresh or not GP_MANIFEST.is_file():
            if refresh and GP_CSV.is_file():
                GP_CSV.unlink()
            _write_json(GP_MANIFEST, fetch_gp(client))
            print(f"fetched GP practices -> {GP_MANIFEST}")
        first = True
        for prop in props:
            path = osm_raw_path(prop.id)
            if path.is_file() and not refresh:
                continue
            if not first:
                time.sleep(PAUSE_S)  # be polite to the public Overpass instance
            first = False
            _write_json(path, fetch_overpass(client, prop))
            print(f"fetched Overpass for {prop.id} -> {path}")


def summary(cache: LocationCacheFile) -> str:
    counts = ", ".join(f"{e.kind.value} {len(e.places)}" for e in cache.nearby)
    return f"{cache.property_id}: {counts}"


# --- check ------------------------------------------------------------------------------


def check(props: list[Property], cache_dir: Path = LOCATION_CACHE_DIR) -> list[str]:
    """Problems with the committed cache (empty list = fine). Never touches the network."""
    problems: list[str] = []
    caches: dict[str, LocationCacheFile] = {}
    for prop in props:
        path = cache_path(prop.id, cache_dir)
        if not path.is_file():
            problems.append(f"{prop.id}: no cache file {path.name}")
            continue
        try:
            cache = read_cache(path)
        except LocationCacheError as exc:
            problems.append(f"{prop.id}: {exc}")
            continue
        caches[prop.id] = cache
        lat, lon = _coords(prop)
        if not _close(cache.origin, Point(latitude=lat, longitude=lon)):
            problems.append(f"{prop.id}: cache origin doesn't match the seed coordinates")
        kinds = {e.kind: e for e in cache.nearby}
        for kind in PlaceKind:
            entry = kinds.get(kind)
            if entry is None:
                problems.append(f"{prop.id}: {kind.value} not searched")
            elif entry.radius_m < RADIUS_M:
                problems.append(f"{prop.id}: {kind.value} searched only to {entry.radius_m:g} m")
        gp = kinds.get(PlaceKind.gp_surgery)
        if gp is not None and gp.source != GP_ENTRY_SOURCE:
            problems.append(f"{prop.id}: gp_surgery entry doesn't name both GP sources")
    raw_present = GP_MANIFEST.is_file() and GP_CSV.is_file()
    raw_present = raw_present and all(osm_raw_path(p.id).is_file() for p in props)
    if raw_present and not problems:
        rebuilt = build_all(props, cache_dir)
        for prop_id, cache in caches.items():
            if rebuilt[prop_id].nearby != cache.nearby:
                problems.append(f"{prop_id}: cache differs from the raw files; re-run the script")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate the cache (no network)")
    mode.add_argument("--offline", action="store_true", help="build from raw files only")
    mode.add_argument("--refresh", action="store_true", help="re-fetch all raw data")
    args = parser.parse_args(argv)
    props = load_seed().list()
    try:
        if args.check:
            problems = check(props)
            for problem in problems:
                print(problem, file=sys.stderr)
            if not problems:
                print(
                    f"location cache is valid for {len(props)} seed properties ({SEED_PATH.name})"
                )
            return 1 if problems else 0
        if not args.offline:
            fetch_missing(props, refresh=args.refresh)
        caches = build_all(props)
    except (IngestError, httpx.HTTPError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for cache in caches.values():
        write_cache(cache)
        print(summary(cache))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
