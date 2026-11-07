"""``ofgem_cap``: Ofgem price cap, Southern Scotland, from the editable config.

``data/config/ofgem_cap.yml`` is meant to be edited by hand each quarter when the cap
changes: update the rates, ``as_of`` / ``valid_from`` / ``valid_to`` and ``retrieved_at``,
then run ``scripts/build_seeds.py``. ``tests/datasets`` checks it against
``data/reference/energy_rates.yaml`` whenever both describe the same cap period.
"""

from datetime import date
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.config import REPO_ROOT
from haven.datasets.seeds import SeedDocument, seed_document

DATASET_ID = "ofgem_cap"
CONFIG_PATH = REPO_ROOT / "data" / "config" / "ofgem_cap.yml"


class FuelCap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unit_rate_p_per_kwh: float = Field(gt=0)
    standing_charge_p_per_day: float = Field(ge=0)
    vat_rate: float = Field(ge=0, le=1)


class OfgemCapConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_url: str = Field(pattern=r"^https?://\S+$")
    licence_note: str = Field(min_length=1)
    as_of: date
    retrieved_at: date
    region: Literal["Southern Scotland"]
    payment_method: Literal["direct_debit"]
    prices_include_vat: Literal[True]
    valid_from: date
    valid_to: date
    electricity: FuelCap
    gas: FuelCap

    @model_validator(mode="after")
    def _check_period(self) -> Self:
        if self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


def load_config() -> OfgemCapConfig:
    return OfgemCapConfig.model_validate(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))


def build() -> SeedDocument:
    config = load_config()
    records = [
        {
            "region": config.region,
            "payment_method": config.payment_method,
            "fuel": fuel,
            "unit_rate_p_per_kwh": rates.unit_rate_p_per_kwh,
            "standing_charge_p_per_day": rates.standing_charge_p_per_day,
            "vat_rate": rates.vat_rate,
            "prices_include_vat": True,
            "valid_from": config.valid_from.isoformat(),
            "valid_to": config.valid_to.isoformat(),
            "is_sample": False,
        }
        for fuel, rates in (("electricity", config.electricity), ("gas", config.gas))
    ]
    return seed_document(
        DATASET_ID,
        source_url=config.source_url,
        as_of=config.as_of,
        retrieved_at=config.retrieved_at,
        licence_note=config.licence_note,
        records=records,
    )
