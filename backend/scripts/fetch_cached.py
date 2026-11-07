"""Fetch OpenStreetMap (Overpass) and NaPTAN data ONCE for the three Edinburgh demo areas.

Rules this script enforces:

- Three demo areas only (Leith, Marchmont, Gorgie; anchors in
  ``haven.datasets.loaders.sample_flats.AREAS``). No other area can be requested.
- One request at a time, with a pause between requests, and a descriptive User-Agent.
- Raw responses are cached under ``data/cache/<source>/`` as JSON named
  ``<area>_<query-hash>_<UTC timestamp>.json``, wrapping the raw body with the query, its
  hash, the URL and the fetch time.
- **Never refetch**: if a cache file with the same query hash exists, the request is skipped.
  Delete the file deliberately to refresh it.
- No Nominatim calls at all; the demo-area points were geocoded once, offline.

Overpass: footways and streets with their surface, smoothness, incline and sidewalk tags, plus
kerb nodes, within ``RADIUS_M`` of each anchor. If Overpass is unavailable, use the Geofabrik
Scotland extract (https://download.geofabrik.de/europe/united-kingdom/scotland.html) offline
instead; it's the same OSM data. Data © OpenStreetMap contributors, ODbL 1.0.

NaPTAN: one request for ATCO area 620 (City of Edinburgh), cached raw; bus stops (stop types
BCT/BCS/BCQ) near the demo areas are extracted at read time by :func:`naptan_bus_stops`.
Contains public sector information licensed under the Open Government Licence v3.0.

Usage (from ``backend/``)::

    uv run python scripts/fetch_cached.py              # fetch whatever isn't cached yet
    uv run python scripts/fetch_cached.py --dry-run    # print what would be fetched
    uv run python scripts/fetch_cached.py --only naptan
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from haven.config import CACHE_DIR
from haven.datasets.loaders.sample_flats import AREAS, Area

USER_AGENT = (
    "haven-prototype/0.1 (Edinburgh renter-check prototype; one-off fetch for three demo "
    "areas; https://github.com/ToweringPluto/haven)"
)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NAPTAN_URL = "https://naptan.api.dft.gov.uk/v1/access-nodes"
NAPTAN_PARAMS = {"dataFormat": "csv", "atcoAreaCodes": "620"}  # 620 = City of Edinburgh
RADIUS_M = 800
PAUSE_S = 5.0
TIMEOUT_S = 120.0
BUS_STOP_TYPES = {"BCT", "BCS", "BCQ"}

PEDESTRIAN_HIGHWAYS = (
    "footway|pedestrian|path|steps|living_street|residential|service|unclassified|"
    "tertiary|secondary|primary|cycleway"
)


@dataclass(frozen=True)
class Request:
    source: str  # "overpass" or "naptan"
    area: str  # demo-area slug, or "edinburgh" for the single NaPTAN request
    method: str
    url: str
    params: dict[str, str]
    body: str | None

    @property
    def query_hash(self) -> str:
        key = json.dumps(
            {"url": self.url, "params": self.params, "body": self.body}, sort_keys=True
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def cached(self) -> Path | None:
        matches = sorted((CACHE_DIR / self.source).glob(f"{self.area}_{self.query_hash}_*.json"))
        return matches[-1] if matches else None


def overpass_query(area: Area) -> str:
    around = f"around:{RADIUS_M},{area.latitude},{area.longitude}"
    return (
        "[out:json][timeout:90];\n"
        "(\n"
        f'  way({around})["highway"~"^({PEDESTRIAN_HIGHWAYS})$"];\n'
        f'  node({around})["kerb"];\n'
        f'  node({around})["barrier"="kerb"];\n'
        f'  node({around})["highway"="crossing"];\n'
        ");\n"
        "out tags geom;\n"
    )


def planned_requests(only: set[str] | None = None) -> list[Request]:
    requests: list[Request] = []
    if only is None or "overpass" in only:
        for slug, area in AREAS.items():
            requests.append(
                Request("overpass", slug, "POST", OVERPASS_URL, {}, overpass_query(area))
            )
    if only is None or "naptan" in only:
        requests.append(Request("naptan", "edinburgh", "GET", NAPTAN_URL, NAPTAN_PARAMS, None))
    return requests


def fetch(client: httpx.Client, request: Request) -> Path:
    fetched_at = datetime.now(UTC)
    if request.method == "POST":
        response = client.post(request.url, data={"data": request.body or ""})
    else:
        response = client.get(request.url, params=request.params)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    raw: Any = response.json() if "json" in content_type else response.text
    stamp = fetched_at.strftime("%Y%m%dT%H%M%SZ")
    path = CACHE_DIR / request.source / f"{request.area}_{request.query_hash}_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = {
        "source": request.source,
        "area": request.area,
        "query_hash": request.query_hash,
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "url": str(response.url),
        "method": request.method,
        "query": request.body,
        "params": request.params,
        "user_agent": USER_AGENT,
        "content_type": content_type,
        "licence": (
            "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)"
            if request.source == "overpass"
            else "NaPTAN, Department for Transport. Open Government Licence v3.0."
        ),
        "raw": raw,
    }
    path.write_text(json.dumps(wrapper, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path


def naptan_bus_stops(cache_file: Path, radius_m: float = 1500) -> list[dict[str, Any]]:
    """Active bus stops from a cached NaPTAN CSV within ``radius_m`` of any demo area."""
    wrapper = json.loads(cache_file.read_text(encoding="utf-8"))
    rows = csv.DictReader(io.StringIO(str(wrapper["raw"]).lstrip("﻿")))
    stops = []
    for row in rows:
        if row.get("StopType") not in BUS_STOP_TYPES or row.get("Status", "active") != "active":
            continue
        try:
            lat, lon = float(row["Latitude"]), float(row["Longitude"])
        except (KeyError, ValueError):
            continue
        near = [s for s, a in AREAS.items() if _metres(lat, lon, a) <= radius_m]
        if near:
            stops.append(
                {
                    "atco_code": row.get("ATCOCode"),
                    "name": row.get("CommonName"),
                    "indicator": row.get("Indicator"),
                    "latitude": lat,
                    "longitude": lon,
                    "areas": near,
                    "is_sample": False,
                }
            )
    return stops


def _metres(lat: float, lon: float, area: Area) -> float:
    dlat = math.radians(lat - area.latitude)
    dlon = math.radians(lon - area.longitude) * math.cos(math.radians(area.latitude))
    return 6_371_000 * math.hypot(dlat, dlon)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", choices=["overpass", "naptan"], action="append")
    parser.add_argument("--dry-run", action="store_true", help="list requests, fetch nothing")
    args = parser.parse_args(argv)
    todo = planned_requests(set(args.only) if args.only else None)
    first = True
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S, follow_redirects=True
    ) as client:
        for request in todo:
            existing = request.cached()
            label = f"{request.source}/{request.area} [{request.query_hash}]"
            if existing is not None:
                print(f"cached {label}: {existing.name} (not refetching)")
                continue
            if args.dry_run:
                print(f"would fetch {label}: {request.method} {request.url}")
                continue
            if not first:
                time.sleep(PAUSE_S)  # one request at a time, politely spaced
            first = False
            try:
                path = fetch(client, request)
            except httpx.HTTPError as exc:
                print(f"error {label}: {exc}; stopping (no retries)", file=sys.stderr)
                return 1
            print(f"fetched {label} -> {path.relative_to(CACHE_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
