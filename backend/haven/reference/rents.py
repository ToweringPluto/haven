"""Typed schema for ``data/reference/rents_lothian_brma.yaml``.

The file holds the Scottish Government's Private Sector Rent Statistics for the **Lothian Broad
Rental Market Area (BRMA)**, latest year only: lower quartile, median, mean and upper quartile
monthly rent (GBP per calendar month) and the number of records, per bedroom category. It is
produced by ``backend/scripts/ingest_rents.py`` from the publication's "Private Rents Open
Data" CSV; never edit the figures by hand.

What the figures are, and are not:

- They come from Rent Service Scotland's Market Evidence Database and are **mostly advertised
  rents** at tenant turnover or for properties new to the market, not the rents sitting
  tenants pay.
- Lothian BRMA is wider than the City of Edinburgh (it also covers neighbouring council areas).
- Each year runs to the end of September. Studios/bedsits and 5+ bedroom properties are not
  published, so :meth:`RentReference.for_bedrooms` returns ``None`` for them (insufficient,
  never a default).
- They are **context** for a listing's rent, not a valuation of any property.
"""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.reference.loader import ReferenceDocument, load_reference

FILE_NAME = "rents_lothian_brma"


class RentStatistics(BaseModel):
    """Monthly rent distribution for one bedroom category (GBP per calendar month)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lower_quartile_gbp_pcm: float = Field(gt=0)
    median_gbp_pcm: float = Field(gt=0)
    mean_gbp_pcm: float = Field(gt=0)
    upper_quartile_gbp_pcm: float = Field(gt=0)
    n_records: int = Field(gt=0, description="Market evidence records behind the figures.")

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if not self.lower_quartile_gbp_pcm <= self.median_gbp_pcm <= self.upper_quartile_gbp_pcm:
            raise ValueError("rents must satisfy lower quartile <= median <= upper quartile")
        return self


class RentsByBedrooms(BaseModel):
    """Bedroom categories published for a BRMA (studios and 5+ bedrooms are not published)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shared_1_bedroom: RentStatistics = Field(
        description="'1 Bedroom Shared' in the source: one bedroom in a shared property."
    )
    bedrooms_1: RentStatistics
    bedrooms_2: RentStatistics
    bedrooms_3: RentStatistics
    bedrooms_4: RentStatistics


class RentReference(ReferenceDocument):
    """``rents_lothian_brma.yaml``: Private Sector Rent Statistics, Lothian BRMA, latest year."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    publisher: Literal["Scottish Government"]
    publication: str = Field(min_length=1)
    published: date
    brma: Literal["Lothian"]
    basis: Literal["mostly_advertised_rents"]
    unit: Literal["gbp_per_calendar_month"]
    year: int = Field(ge=2010, description="Statistics year, running to the end of September.")
    period_end: date = Field(description="Last day of the statistics year (30 September).")
    source_url: str = Field(pattern=r"^https?://\S+$", description="Open data CSV.")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="sha256 of the CSV.")
    methodology_url: str = Field(pattern=r"^https?://\S+$")
    rents: RentsByBedrooms

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.period_end != date(self.year, 9, 30):
            raise ValueError("period_end must be 30 September of the statistics year")
        if self.published <= self.period_end:
            raise ValueError("published must be after period_end")
        return self

    def for_bedrooms(self, bedrooms: int) -> RentStatistics | None:
        """Statistics for a self-contained property with ``bedrooms`` bedrooms.

        ``None`` (insufficient) for studios (0) and 5+ bedrooms, which are not published.
        """
        match bedrooms:
            case 1:
                return self.rents.bedrooms_1
            case 2:
                return self.rents.bedrooms_2
            case 3:
                return self.rents.bedrooms_3
            case 4:
                return self.rents.bedrooms_4
            case _:
                return None


def load_rents() -> RentReference:
    """Load the committed Lothian BRMA rent reference file."""
    return load_reference(FILE_NAME, RentReference)
