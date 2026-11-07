"""The reference data the cost engine reads, bundled so tests can substitute it."""

from dataclasses import dataclass
from functools import lru_cache

from haven.reference import (
    CouncilTaxReference,
    ElectricityUseReference,
    EnergyModelReference,
    EnergyRatesReference,
    HeatingEfficiencyReference,
    load_council_tax,
    load_electricity_use,
    load_energy_model,
    load_energy_rates,
    load_heating_efficiency,
)


@dataclass(frozen=True)
class CostReferences:
    """Council tax charges, price cap rates, EPC heat demand, TDCVs and SAP efficiencies."""

    council_tax: CouncilTaxReference
    energy_rates: EnergyRatesReference
    energy_model: EnergyModelReference
    electricity_use: ElectricityUseReference
    heating_efficiency: HeatingEfficiencyReference


@lru_cache(maxsize=1)
def load_cost_references() -> CostReferences:
    """Load (once per process) the committed reference files the cost engine needs."""
    return CostReferences(
        council_tax=load_council_tax(),
        energy_rates=load_energy_rates(),
        energy_model=load_energy_model(),
        electricity_use=load_electricity_use(),
        heating_efficiency=load_heating_efficiency(),
    )
