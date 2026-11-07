"""Typed schema for ``data/reference/energy_kwh_per_m2_edinburgh.yaml``.

The file holds distributions (median and interquartile range, with counts) of **calculated
annual heat demand per m² of floor area** for City of Edinburgh dwellings, derived from the
Scottish domestic EPC register by ``backend/scripts/ingest_epc.py``. Never edit it by hand.

What the figures are:

- ``SPACE_HEATING_DEMAND + WATER_HEATING_DEMAND`` (kWh/year, as calculated by SAP/RdSAP under
  standardised occupancy) divided by ``TOTAL_FLOOR_AREA`` (m²). These are modelled demands
  recorded on EPCs, not metered consumption, and they are heat demand, not fuel bought.
- **Lighting is not included**: the dataset has no lighting kWh column, only a lighting cost
  (``LIGHTING_COST_CURRENT``, GBP over 3 years at the assessment's fuel prices). Callers must
  report lighting/appliance electricity separately or as not estimated, never fold it in.

Groups are (EPC band × property type × main heating fuel), kept only when they have at least
``min_group_n`` certificates; ``band_groups`` (EPC band only) are the fallback. ``lookup``
returns which level matched so callers can say so, or ``None`` when neither has enough data.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.domain import EpcBand, MainFuel, PropertyType
from haven.reference.loader import ReferenceDocument, load_reference

FILE_NAME = "energy_kwh_per_m2_edinburgh"
MIN_GROUP_N = 30

GroupLevel = Literal["band_type_fuel", "band"]


class Distribution(BaseModel):
    """Median and quartiles of kWh per m² per year over ``n`` certificates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n: int = Field(ge=1, description="Number of certificates in the group.")
    median: float = Field(ge=0, description="Median kWh/m²/year.")
    q1: float = Field(ge=0, description="25th percentile kWh/m²/year.")
    q3: float = Field(ge=0, description="75th percentile kWh/m²/year.")

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if not self.q1 <= self.median <= self.q3:
            raise ValueError("expected q1 <= median <= q3")
        return self


class BandGroup(Distribution):
    epc_band: EpcBand


class DetailGroup(Distribution):
    epc_band: EpcBand
    property_type: PropertyType
    main_fuel: MainFuel


class GroupMatch(BaseModel):
    """The group ``lookup`` matched and at which level (detailed or band-only fallback)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: GroupLevel
    distribution: Distribution


class RecordCounts(BaseModel):
    """How many Edinburgh certificates were read, removed and used."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    read: int = Field(ge=0, description="Edinburgh City rows read from the CSVs.")
    duplicates_removed: int = Field(
        ge=0, description="Older certificates for the same BUILDING_REFERENCE_NUMBER."
    )
    excluded: dict[str, int] = Field(description="Rows dropped, by reason.")
    used: int = Field(ge=0, description="Certificates in the band-level distributions.")
    without_property_type: int = Field(
        ge=0, description="Used for band groups only: property type blank or unrecognised."
    )
    without_main_fuel: int = Field(
        ge=0, description="Used for band groups only: main heating fuel blank or ambiguous."
    )

    @model_validator(mode="after")
    def _check_sum(self) -> Self:
        if self.read - self.duplicates_removed - sum(self.excluded.values()) != self.used:
            raise ValueError("read - duplicates_removed - excluded must equal used")
        return self


class EnergyModelReference(ReferenceDocument):
    """``energy_kwh_per_m2_edinburgh.yaml``: heat demand per m² by EPC band, type and fuel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_authority: Literal["Edinburgh City"]
    dataset_release: str = Field(min_length=1)
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metric: Literal["space_and_water_heating_demand_kwh_per_m2_year"]
    numerator_columns: list[str]
    denominator_column: Literal["TOTAL_FLOOR_AREA"]
    lighting_included: Literal[False]
    min_group_n: int = Field(ge=1)
    quantile_method: Literal["inclusive"]
    records: RecordCounts
    band_groups: list[BandGroup]
    groups: list[DetailGroup]

    @model_validator(mode="after")
    def _check_groups(self) -> Self:
        bands = [g.epc_band for g in self.band_groups]
        if len(set(bands)) != len(bands):
            raise ValueError("duplicate EPC band in band_groups")
        keys = [(g.epc_band, g.property_type, g.main_fuel) for g in self.groups]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate (band, type, fuel) in groups")
        small = [g for g in [*self.band_groups, *self.groups] if g.n < self.min_group_n]
        if small:
            raise ValueError(f"{len(small)} group(s) have n < min_group_n")
        return self

    def lookup(
        self,
        epc_band: EpcBand,
        property_type: PropertyType | None = None,
        main_fuel: MainFuel | None = None,
    ) -> GroupMatch | None:
        """Most specific distribution with enough data, or ``None`` (treat as insufficient)."""
        if property_type is not None and main_fuel is not None:
            for g in self.groups:
                if (g.epc_band, g.property_type, g.main_fuel) == (
                    epc_band,
                    property_type,
                    main_fuel,
                ):
                    return GroupMatch(level="band_type_fuel", distribution=_dist(g))
        for b in self.band_groups:
            if b.epc_band == epc_band:
                return GroupMatch(level="band", distribution=_dist(b))
        return None


def _dist(group: Distribution) -> Distribution:
    return Distribution(n=group.n, median=group.median, q1=group.q1, q3=group.q3)


def load_energy_model() -> EnergyModelReference:
    """Load the committed Edinburgh EPC heat-demand reference file."""
    return load_reference(FILE_NAME, EnergyModelReference)
