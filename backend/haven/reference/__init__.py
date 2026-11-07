"""Reference data (``data/reference/*.yaml``) with mandatory provenance metadata."""

from haven.reference.council_tax import (
    BandCharges,
    CouncilTaxReference,
    CouncilTaxYear,
    load_council_tax,
)
from haven.reference.electricity_use import (
    ElectricityUseReference,
    UsageLevels,
    load_electricity_use,
)
from haven.reference.energy_model import (
    BandGroup,
    DetailGroup,
    Distribution,
    EnergyModelReference,
    GroupMatch,
    load_energy_model,
)
from haven.reference.energy_rates import EnergyRatesReference, FuelRates, load_energy_rates
from haven.reference.loader import (
    ReferenceDataError,
    ReferenceDocument,
    ReferenceMeta,
    iter_reference_files,
    load_all_references,
    load_reference,
    load_reference_file,
)
from haven.reference.rents import RentReference, RentsByBedrooms, RentStatistics, load_rents

__all__ = [
    "BandCharges",
    "BandGroup",
    "CouncilTaxReference",
    "CouncilTaxYear",
    "DetailGroup",
    "Distribution",
    "ElectricityUseReference",
    "EnergyModelReference",
    "EnergyRatesReference",
    "FuelRates",
    "GroupMatch",
    "ReferenceDataError",
    "ReferenceDocument",
    "ReferenceMeta",
    "RentReference",
    "RentStatistics",
    "RentsByBedrooms",
    "UsageLevels",
    "iter_reference_files",
    "load_all_references",
    "load_council_tax",
    "load_electricity_use",
    "load_energy_model",
    "load_energy_rates",
    "load_reference",
    "load_reference_file",
    "load_rents",
]
