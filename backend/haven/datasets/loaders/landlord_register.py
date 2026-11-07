"""``landlord_register``: FAKE landlord registration numbers for the sample flats.

The Scottish Landlord Register is never scraped or queried in bulk. Haven seeds obviously
fake numbers (prefix ``SAMPLE-``, which can't match a real registration) and links renters to
the official search page to check a real landlord themselves.
"""

from datetime import date

from haven.datasets.seeds import SeedDocument, seed_document

DATASET_ID = "landlord_register"
SEARCH_URL = "https://www.landlordregistrationscotland.gov.uk/search"
AS_OF = date(2026, 11, 7)
COUNT = 8
LICENCE_NOTE = (
    "Invented sample data, same licence as this repository. No data is taken from the "
    "Scottish Landlord Register; check a real landlord at " + SEARCH_URL
)


def registration_number(index: int) -> str:
    if not 1 <= index <= COUNT:
        raise ValueError(f"no fake landlord {index}")
    return f"SAMPLE-LR-{index:04d}"


def build() -> SeedDocument:
    records = [
        {
            "registration_number": registration_number(i),
            "landlord_name": f"Sample Landlord {chr(64 + i)} (invented)",
            "status": "sample",
            "check_url": SEARCH_URL,
            "is_sample": True,
        }
        for i in range(1, COUNT + 1)
    ]
    return seed_document(
        DATASET_ID,
        source_url=SEARCH_URL,
        as_of=AS_OF,
        retrieved_at=AS_OF,
        licence_note=LICENCE_NOTE,
        records=records,
    )
