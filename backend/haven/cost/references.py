"""The reference data the cost engine reads, bundled so tests can substitute it."""

from dataclasses import dataclass
from functools import lru_cache

from haven.reference import (
    CouncilTaxReference,
    ElectricityUseReference,
    EnergyModelReference,
    EnergyRatesReference,
    load_council_tax,
    load_electricity_use,
    load_energy_model,
    load_energy_rates,
)


@dataclass(frozen=True)
class CostReferences:
    """Council tax charges, energy price cap rates, EPC heat demand model and TDCVs."""

    council_tax: CouncilTaxReference
    energy_rates: EnergyRatesReference
    energy_model: EnergyModelReference
    electricity_use: ElectricityUseReference


@lru_cache(maxsize=1)
def load_cost_references() -> CostReferences:
    """Load (once per process) the committed reference files the cost engine needs."""
    return CostReferences(
        council_tax=load_council_tax(),
        energy_rates=load_energy_rates(),
        energy_model=load_energy_model(),
        electricity_use=load_electricity_use(),
    )
