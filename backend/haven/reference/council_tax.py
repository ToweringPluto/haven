"""Typed schema for ``data/reference/council_tax_edinburgh.yaml``.

The file holds the City of Edinburgh Council's annual charges per council tax band for each
financial year: council tax, plus the Scottish Water water and waste water (sewerage) charges
that are billed with it. It is produced by ``backend/scripts/ingest_council_tax.py`` from the
council's own PDFs; never edit the figures by hand.

The charges are the full annual amounts before any discount, exemption or Council Tax
Reduction (e.g. single-person discount, full-time student exemption), which aren't modelled.
"""

import re
from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.domain import CouncilTaxBand
from haven.reference.loader import ReferenceDocument, load_reference

FILE_NAME = "council_tax_edinburgh"
YEAR_PATTERN = r"^\d{4}/\d{2}$"


def to_pence(amount_gbp: float) -> int:
    """Round a GBP amount to whole pence (for exact sum checks)."""
    return round(amount_gbp * 100)


class BandCharges(BaseModel):
    """Annual charges for one band, in GBP, exactly as printed by the council."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    council_tax_gbp: float = Field(gt=0)
    water_gbp: float = Field(gt=0)
    waste_water_gbp: float = Field(gt=0)
    total_gbp: float = Field(gt=0, description="Council tax + water + waste water.")

    @model_validator(mode="after")
    def _total_is_sum(self) -> Self:
        parts = to_pence(self.council_tax_gbp) + to_pence(self.water_gbp)
        parts += to_pence(self.waste_water_gbp)
        if parts != to_pence(self.total_gbp):
            raise ValueError(
                f"total {self.total_gbp} != council tax + water + waste water ({parts / 100:.2f})"
            )
        return self


class CouncilTaxYear(BaseModel):
    """Charges for one financial year, with the source document they were parsed from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_url: str = Field(pattern=r"^https?://\S+$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="sha256 of the PDF.")
    valid_from: date
    valid_to: date
    bands: dict[CouncilTaxBand, BandCharges]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        missing = set(CouncilTaxBand) - set(self.bands)
        if missing:
            raise ValueError(f"missing bands: {sorted(missing)}")
        totals = [self.bands[b].total_gbp for b in CouncilTaxBand]
        if totals != sorted(totals):
            raise ValueError("band totals must increase from A to H")
        return self


class CouncilTaxReference(ReferenceDocument):
    """``council_tax_edinburgh.yaml``: annual charges per band, keyed by year ("2025/26")."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    authority: Literal["City of Edinburgh Council"]
    currency: Literal["GBP"]
    period: Literal["annual"]
    years: dict[str, CouncilTaxYear] = Field(min_length=1)

    @model_validator(mode="after")
    def _year_keys(self) -> Self:
        for key, year in self.years.items():
            if not re.match(YEAR_PATTERN, key):
                raise ValueError(f"year key {key!r} must look like '2025/26'")
            start = int(key[:4])
            if year.valid_from.year != start or int(key[5:]) != (start + 1) % 100:
                raise ValueError(f"year key {key!r} doesn't match valid_from {year.valid_from}")
        return self

    def year_for(self, on: date) -> CouncilTaxYear | None:
        """The year whose validity period contains ``on``, or ``None`` if none does."""
        for year in self.years.values():
            if year.valid_from <= on <= year.valid_to:
                return year
        return None


def load_council_tax() -> CouncilTaxReference:
    """Load the committed Edinburgh council tax reference file."""
    return load_reference(FILE_NAME, CouncilTaxReference)
