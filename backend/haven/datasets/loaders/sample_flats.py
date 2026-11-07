"""``sample_flats``: 20 INVENTED flats across three Edinburgh demo areas.

Nothing here is a real address, landlord or listing. Every record has ``is_sample: true``.
Rents, sizes, floors, lifts, steps and bands are hand-chosen illustrative values.

Coordinates were geocoded once, offline, for the three demo areas only: each flat carries its
area's anchor point (a point on a public street, from OpenStreetMap via a single Nominatim
lookup each, recorded in ``scripts/make_seed.py``), not a building position. No bulk
geocoding is done, and none is needed.
"""

from datetime import date
from typing import NamedTuple

from haven.datasets.loaders.landlord_register import registration_number
from haven.datasets.seeds import SeedDocument, seed_document

DATASET_ID = "sample_flats"
AS_OF = date(2026, 11, 7)
SOURCE_URL = "https://github.com/ToweringPluto/haven/blob/main/data/seed/sample_flats.json"
LICENCE_NOTE = (
    "Invented sample data, same licence as this repository. Area anchor points: "
    "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)."
)
LABEL = "Sample flat (invented, not a real listing)"


class Area(NamedTuple):
    slug: str
    name: str
    anchor_street: str
    latitude: float
    longitude: float


# The three demo areas; anchors match data/seed/properties.yaml (OSM street ways).
AREAS = {
    "leith": Area("leith", "Leith", "Great Junction Street", 55.97217, -3.17449),
    "marchmont": Area("marchmont", "Marchmont", "Marchmont Crescent", 55.93925, -3.19373),
    "gorgie": Area("gorgie", "Gorgie", "Wheatfield Street", 55.93805, -3.23377),
}


class Flat(NamedTuple):
    area: str
    bedrooms: int
    floor: int  # 0 = ground floor
    has_lift: bool
    entrance_steps: int
    rent_pcm_gbp: int
    epc_band: str
    council_tax_band: str
    main_fuel: str
    floor_area_m2: int
    landlord: int  # index into the fake landlord register


FLATS: list[Flat] = [
    Flat("leith", 1, 0, False, 2, 895, "D", "B", "mains_gas", 45, 1),
    Flat("leith", 2, 3, False, 4, 1150, "C", "C", "mains_gas", 62, 2),
    Flat("leith", 2, 4, True, 0, 1395, "B", "D", "electricity", 70, 3),
    Flat("leith", 1, 1, False, 3, 950, "D", "B", "mains_gas", 48, 1),
    Flat("leith", 3, 2, False, 5, 1500, "D", "D", "mains_gas", 85, 4),
    Flat("leith", 1, 0, False, 0, 875, "E", "A", "electricity", 40, 2),
    Flat("leith", 2, 2, True, 1, 1250, "C", "C", "mains_gas", 66, 3),
    Flat("marchmont", 2, 2, False, 6, 1425, "D", "D", "mains_gas", 78, 5),
    Flat("marchmont", 3, 3, False, 6, 1795, "D", "E", "mains_gas", 105, 5),
    Flat("marchmont", 1, 1, False, 4, 1050, "E", "C", "mains_gas", 52, 6),
    Flat("marchmont", 2, 0, False, 3, 1375, "D", "D", "mains_gas", 74, 4),
    Flat("marchmont", 4, 4, False, 6, 2400, "E", "F", "mains_gas", 130, 6),
    Flat("marchmont", 1, 3, False, 6, 1000, "D", "B", "mains_gas", 47, 5),
    Flat("marchmont", 2, 1, True, 0, 1550, "C", "D", "mains_gas", 72, 7),
    Flat("gorgie", 1, 0, False, 1, 795, "F", "A", "electricity", 42, 8),
    Flat("gorgie", 2, 2, False, 4, 1050, "D", "B", "mains_gas", 60, 7),
    Flat("gorgie", 1, 3, False, 4, 825, "D", "A", "mains_gas", 44, 8),
    Flat("gorgie", 2, 1, True, 0, 1195, "B", "C", "mains_gas", 64, 7),
    Flat("gorgie", 3, 2, False, 4, 1295, "C", "C", "mains_gas", 82, 8),
    Flat("gorgie", 1, 0, False, 0, 850, "C", "A", "electricity", 46, 6),
]


def build() -> SeedDocument:
    counters: dict[str, int] = {}
    records = []
    for flat in FLATS:
        area = AREAS[flat.area]
        counters[area.slug] = counters.get(area.slug, 0) + 1
        records.append(
            {
                "id": f"sample-{area.slug}-{counters[area.slug]:02d}",
                "label": LABEL,
                "area": area.name,
                "anchor_street": area.anchor_street,
                "latitude": area.latitude,
                "longitude": area.longitude,
                "location_precision": "area_anchor",
                "property_type": "flat",
                "bedrooms": flat.bedrooms,
                "floor_area_m2": flat.floor_area_m2,
                "floor": flat.floor,
                "has_lift": flat.has_lift,
                "entrance_steps": flat.entrance_steps,
                "step_free": flat.entrance_steps == 0 and (flat.floor == 0 or flat.has_lift),
                "rent_pcm_gbp": flat.rent_pcm_gbp,
                "epc_band": flat.epc_band,
                "council_tax_band": flat.council_tax_band,
                "main_fuel": flat.main_fuel,
                "landlord_registration_number": registration_number(flat.landlord),
                "is_sample": True,
            }
        )
    return seed_document(
        DATASET_ID,
        source_url=SOURCE_URL,
        as_of=AS_OF,
        retrieved_at=AS_OF,
        licence_note=LICENCE_NOTE,
        records=records,
    )
