"""``council_tax``: City of Edinburgh band -> annual charge, 2026/27.

Built from ``data/reference/council_tax_edinburgh.yaml`` (parsed from the council's
"Council tax charges 2026" PDF by ``scripts/ingest_council_tax.py``). Charges include
Scottish Water's water and waste water charges, before any discount or exemption.
"""

from haven.datasets.seeds import SeedDocument, seed_document
from haven.reference import load_council_tax

DATASET_ID = "council_tax"
YEAR = "2026/27"


def build() -> SeedDocument:
    reference = load_council_tax()
    year = reference.years[YEAR]
    records = [
        {
            "authority": reference.authority,
            "year": YEAR,
            "band": band.value,
            "council_tax_gbp": charges.council_tax_gbp,
            "water_gbp": charges.water_gbp,
            "waste_water_gbp": charges.waste_water_gbp,
            "annual_total_gbp": charges.total_gbp,
            "monthly_total_gbp": round(charges.total_gbp / 12, 2),
            "valid_from": year.valid_from.isoformat(),
            "valid_to": year.valid_to.isoformat(),
            "is_sample": False,
        }
        for band, charges in sorted(year.bands.items())
    ]
    return seed_document(
        DATASET_ID,
        source_url=year.source_url,
        as_of=year.valid_from,
        retrieved_at=reference.meta.retrieved,
        licence_note=reference.meta.licence,
        records=records,
    )
