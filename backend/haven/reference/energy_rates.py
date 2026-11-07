"""Typed schema for ``data/reference/energy_rates.yaml``.

The file holds Ofgem's energy price cap unit rates and standing charges for one cap period,
for the **Southern Scotland** electricity region (which covers Edinburgh's EH postcodes), for
customers paying by **Direct Debit** on a default (capped) tariff: single-rate electricity and
gas. It is produced by ``backend/scripts/ingest_energy_rates.py`` from Ofgem's published
tables; never edit the figures by hand.

The figures are caps on default tariffs, not any renter's actual tariff, and they change every
quarter, so callers must check ``covers(date)`` and treat an out-of-period date as unknown rather
than silently reusing old rates.
"""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.reference.loader import ReferenceDocument, load_reference

FILE_NAME = "energy_rates"


class FuelRates(BaseModel):
    """Capped unit rate and daily standing charge for one fuel, as Ofgem publishes them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    unit_rate_p_per_kwh: float = Field(gt=0, description="Pence per kWh, VAT at vat_rate included.")
    standing_charge_p_per_day: float = Field(
        ge=0, description="Pence per day, VAT at vat_rate included."
    )
    vat_rate: float = Field(ge=0, le=1, description="VAT rate already included (0.05 = 5%).")
    source_url: str = Field(
        pattern=r"^https?://\S+$", description="Ofgem table the rates are from."
    )
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="sha256 of the raw table.")


class EnergyRatesReference(ReferenceDocument):
    """``energy_rates.yaml``: price cap rates for one region, payment method and cap period."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region: Literal["Southern Scotland"]
    payment_method: Literal["direct_debit"]
    tariff: Literal["default_tariff_price_cap"]
    electricity_meter: Literal["single_rate"]
    prices_include_vat: Literal[True]
    valid_from: date
    valid_to: date
    electricity: FuelRates
    gas: FuelRates

    @model_validator(mode="after")
    def _check_period(self) -> Self:
        if self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self

    def covers(self, on: date) -> bool:
        """Whether ``on`` falls inside the cap period these rates apply to."""
        return self.valid_from <= on <= self.valid_to


def load_energy_rates() -> EnergyRatesReference:
    """Load the committed energy price cap reference file."""
    return load_reference(FILE_NAME, EnergyRatesReference)
