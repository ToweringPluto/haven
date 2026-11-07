"""Fetch NaPTAN bus stops for City of Edinburgh ONCE and cache the raw response.

Kerb, incline, surface and crossing data from OpenStreetMap now comes from
``scripts/ingest_osm.py`` (``--enrich``), which stores a per-property summary in
``data/location_cache/``. This script keeps only NaPTAN until it can be merged into the bus-stop
entries there; doing that changes which stop is nearest, so it needs the routes rebuilding
(``scripts/build_routes.py``, which needs an openrouteservice key).

Rules this script enforces:

- One request, for ATCO area 620 (City of Edinburgh) only, with a descriptive User-Agent.
- The raw response is cached under ``data/cache/naptan/`` as JSON named
  ``edinburgh_<query-hash>_<UTC timestamp>.json``, wrapping the raw CSV with the query, its
  hash, the URL and the fetch time.
- **Never refetch**: if a cache file with the same query hash exists, nothing is requested.
  Delete the file deliberately to refresh it.

Bus stops (stop types BCT/BCS/BCQ, status active) near the demo areas are extracted at read
time by :func:`naptan_bus_stops`. Contains public sector information licensed under the Open
Government Licence v3.0.

Usage (from ``backend/``)::

    uv run python scripts/fetch_cached.py            # fetch if not cached yet
    uv run python scripts/fetch_cached.py --dry-run  # print what would be fetched
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from haven.config import CACHE_DIR
from haven.datasets.loaders.sample_flats import AREAS, Area

USER_AGENT = (
    "haven-prototype/0.1 (Edinburgh renter-check prototype; one-off fetch; "
    "https://github.com/ToweringPluto/haven)"
)
NAPTAN_URL = "https://naptan.api.dft.gov.uk/v1/access-nodes"
NAPTAN_PARAMS = {"dataFormat": "csv", "atcoAreaCodes": "620"}  # 620 = City of Edinburgh
TIMEOUT_S = 120.0
BUS_STOP_TYPES = {"BCT", "BCS", "BCQ"}


@dataclass(frozen=True)
class Request:
    source: str
    area: str
    url: str
    params: dict[str, str]

    @property
    def query_hash(self) -> str:
        key = json.dumps({"url": self.url, "params": self.params, "body": None}, sort_keys=True)
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def cached(self) -> Path | None:
        matches = sorted((CACHE_DIR / self.source).glob(f"{self.area}_{self.query_hash}_*.json"))
        return matches[-1] if matches else None


NAPTAN_REQUEST = Request("naptan", "edinburgh", NAPTAN_URL, NAPTAN_PARAMS)


def planned_requests() -> list[Request]:
    return [NAPTAN_REQUEST]


def fetch(client: httpx.Client, request: Request) -> Path:
    fetched_at = datetime.now(UTC)
    response = client.get(request.url, params=request.params)
    response.raise_for_status()
    stamp = fetched_at.strftime("%Y%m%dT%H%M%SZ")
    path = CACHE_DIR / request.source / f"{request.area}_{request.query_hash}_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = {
        "source": request.source,
        "area": request.area,
        "query_hash": request.query_hash,
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "url": str(response.url),
        "method": "GET",
        "query": None,
        "params": request.params,
        "user_agent": USER_AGENT,
        "content_type": response.headers.get("content-type", ""),
        "licence": "NaPTAN, Department for Transport. Open Government Licence v3.0.",
        "raw": response.text,
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
    parser.add_argument("--dry-run", action="store_true", help="list requests, fetch nothing")
    args = parser.parse_args(argv)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S, follow_redirects=True
    ) as client:
        for request in planned_requests():
            existing = request.cached()
            label = f"{request.source}/{request.area} [{request.query_hash}]"
            if existing is not None:
                print(f"cached {label}: {existing.name} (not refetching)")
                continue
            if args.dry_run:
                print(f"would fetch {label}: GET {request.url}")
                continue
            try:
                path = fetch(client, request)
            except httpx.HTTPError as exc:
                print(f"error {label}: {exc}; stopping (no retries)", file=sys.stderr)
                return 1
            print(f"fetched {label} -> {path.relative_to(CACHE_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
