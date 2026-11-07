"""``lha_rates``: Local Housing Allowance rates, Lothian BRMA, April 2026 to March 2027.

Transcribed from the official page (there is no machine-readable table on it):
https://www.gov.scot/publications/local-housing-allowance-rates/pages/2026-to-2027/
("Weekly Scottish LHA report for April 2026 to March 2027 and effective from 1st April 2026",
page last updated 30 January 2026, read 2026-11-07).

- Weekly rates are the published LHA rates. They are **frozen** for 2026-27 at the rate
  determined on 31 January 2024, so they are below current market rents.
- 30th percentiles are the page's "30th percentile market rents September 2025" column (the
  "shadow 30th percentile", 12 months of lettings to end September 2025). The column has no
  unit label; it sits in the weekly report and its values sit just above the weekly rates
  (e.g. 1 bed 214.03 vs 172.60), so it is treated as weekly.
- Monthly = weekly * 52 / 12 (rounded to the penny).
"""

from datetime import date

from haven.datasets.loaders.common import OGL_GOV_SCOT, monthly_from_weekly
from haven.datasets.seeds import SeedDocument, seed_document

DATASET_ID = "lha_rates"
SOURCE_URL = "https://www.gov.scot/publications/local-housing-allowance-rates/pages/2026-to-2027/"
AS_OF = date(2026, 4, 1)
RETRIEVED_AT = date(2026, 11, 7)
BRMA = "Lothian"

# category: (bedrooms, weekly LHA rate GBP, weekly 30th percentile market rent GBP, Sept 2025)
RATES: dict[str, tuple[int, float, float]] = {
    "shared_accommodation": (1, 109.32, 131.18),
    "1_bed": (1, 172.60, 214.03),
    "2_bed": (2, 223.23, 276.16),
    "3_bed": (3, 316.44, 354.41),
    "4_bed": (4, 501.70, 529.32),
}


def build() -> SeedDocument:
    records = [
        {
            "brma": BRMA,
            "category": category,
            "bedrooms": bedrooms,
            "weekly_rate_gbp": weekly,
            "monthly_rate_gbp": monthly_from_weekly(weekly),
            "percentile_30_weekly_gbp": p30,
            "percentile_30_monthly_gbp": monthly_from_weekly(p30),
            "percentile_30_period": "12 months to end September 2025",
            "valid_from": "2026-04-01",
            "valid_to": "2027-03-31",
            "frozen": True,
            "is_sample": False,
        }
        for category, (bedrooms, weekly, p30) in RATES.items()
    ]
    return seed_document(
        DATASET_ID,
        source_url=SOURCE_URL,
        as_of=AS_OF,
        retrieved_at=RETRIEVED_AT,
        licence_note=OGL_GOV_SCOT,
        records=records,
    )
