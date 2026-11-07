"""Reference data (``data/reference/*.yaml``) with mandatory provenance metadata."""

from haven.reference.council_tax import (
    BandCharges,
    CouncilTaxReference,
    CouncilTaxYear,
    load_council_tax,
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

__all__ = [
    "BandCharges",
    "CouncilTaxReference",
    "CouncilTaxYear",
    "EnergyRatesReference",
    "FuelRates",
    "ReferenceDataError",
    "ReferenceDocument",
    "ReferenceMeta",
    "iter_reference_files",
    "load_all_references",
    "load_council_tax",
    "load_energy_rates",
    "load_reference",
    "load_reference_file",
]
