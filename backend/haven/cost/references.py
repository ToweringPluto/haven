"""The reference data the cost engine reads, bundled so tests can substitute it."""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from haven.datasets.seeds import SeedError, load_seed_file
from haven.reference import (
    CouncilTaxReference,
    ElectricityUseReference,
    EnergyModelReference,
    EnergyRatesReference,
    HeatingEfficiencyReference,
    RentReference,
    load_council_tax,
    load_electricity_use,
    load_energy_model,
    load_energy_rates,
    load_heating_efficiency,
    load_rents,
)

LHA_DATASET_ID = "lha_rates"


@dataclass(frozen=True)
class LhaRates:
    """Monthly Local Housing Allowance rates (Lothian) by bedroom count, self-contained homes."""

    monthly_gbp_by_bedrooms: dict[int, float]
    as_of: date
    valid_to: date
    source: str


@dataclass(frozen=True)
class CostReferences:
    """Council tax charges, price cap rates, EPC heat demand, TDCVs and SAP efficiencies.

    ``rents`` and ``lha`` feed the rent context only; ``None`` leaves it out.
    """

    council_tax: CouncilTaxReference
    energy_rates: EnergyRatesReference
    energy_model: EnergyModelReference
    electricity_use: ElectricityUseReference
    heating_efficiency: HeatingEfficiencyReference
    rents: RentReference | None = None
    lha: LhaRates | None = None


def load_lha_rates() -> LhaRates | None:
    """The LHA seed (``data/seed/lha_rates.json``), or ``None`` if it's missing."""
    try:
        seed = load_seed_file(LHA_DATASET_ID)
    except SeedError:
        return None
    rates = {
        int(r["bedrooms"]): float(r["monthly_rate_gbp"])
        for r in seed.records
        if str(r["category"]).endswith("_bed")  # self-contained, not shared accommodation
    }
    valid_to = max(date.fromisoformat(str(r["valid_to"])) for r in seed.records)
    return LhaRates(
        monthly_gbp_by_bedrooms=rates,
        as_of=seed.as_of,
        valid_to=valid_to,
        source="Scottish Government, Local Housing Allowance rates 2026 to 2027 (Lothian)",
    )


@lru_cache(maxsize=1)
def load_cost_references() -> CostReferences:
    """Load (once per process) the committed reference files the cost engine needs."""
    return CostReferences(
        council_tax=load_council_tax(),
        energy_rates=load_energy_rates(),
        energy_model=load_energy_model(),
        electricity_use=load_electricity_use(),
        heating_efficiency=load_heating_efficiency(),
        rents=load_rents(),
        lha=load_lha_rates(),
    )
