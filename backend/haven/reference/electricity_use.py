"""Typed schema for ``data/reference/electricity_lighting_appliances.yaml``.

The file holds Ofgem's Typical Domestic Consumption Values (TDCVs) for **single-rate
electricity meters (Profile Class 1)**: the lower quartile, median and upper quartile of annual
household electricity use in Great Britain, in kWh. It is produced by
``backend/scripts/ingest_electricity_tdcv.py`` from Ofgem's decision PDF; never edit the figures
by hand.

What the figures are, and are not:

- They are **all metered electricity** on single-rate meters (lighting, appliances, and any
  electric cooking or heating in those homes), not a lighting-and-appliances-only measurement.
  For a home heated by gas they are the closest official proxy for non-heating electricity. For
  an electrically heated home, adding them to the EPC heat demand may double-count some heating,
  so callers must say so.
- They are GB-wide and do not depend on floor area or occupants. ``low``/``high`` are quartiles
  of households, not a confidence interval for one property.
"""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.reference.loader import ReferenceDocument, load_reference

FILE_NAME = "electricity_lighting_appliances"


class UsageLevels(BaseModel):
    """Ofgem's low / medium / high usage levels (lower quartile, median, upper quartile)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low_kwh_per_year: int = Field(gt=0, description="Lower quartile of households.")
    medium_kwh_per_year: int = Field(gt=0, description="Median household.")
    high_kwh_per_year: int = Field(gt=0, description="Upper quartile of households.")

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if not self.low_kwh_per_year < self.medium_kwh_per_year < self.high_kwh_per_year:
            raise ValueError("usage levels must satisfy low < medium < high")
        return self


class ElectricityUseReference(ReferenceDocument):
    """``electricity_lighting_appliances.yaml``: Ofgem TDCVs for single-rate electricity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    publisher: Literal["Ofgem"]
    measure: Literal["typical_domestic_consumption_values"]
    geography: Literal["Great Britain"]
    meter: Literal["profile_class_1_single_rate"]
    end_uses: Literal["all_metered_electricity"]
    statistic: Literal["lower_quartile_median_upper_quartile"]
    lighting_and_appliances_only: Literal[False]
    decision_published: date
    valid_from: date = Field(description="Date Ofgem started using these TDCVs.")
    source_url: str = Field(pattern=r"^https?://\S+$", description="Ofgem decision PDF.")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="sha256 of the PDF.")
    method_source_url: str = Field(
        pattern=r"^https?://\S+$",
        description="Ofgem consultation PDF that states the quartile/median method.",
    )
    electricity: UsageLevels

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.valid_from < self.decision_published:
            raise ValueError("valid_from must not be before decision_published")
        return self

    def in_force(self, on: date) -> bool:
        """Whether these TDCVs had taken effect by ``on`` (they stay in force until revised)."""
        return on >= self.valid_from


def load_electricity_use() -> ElectricityUseReference:
    """Load the committed TDCV electricity reference file."""
    return load_reference(FILE_NAME, ElectricityUseReference)
