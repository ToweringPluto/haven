"""Property facts. Every attribute carries its own provenance via ``Evidence``."""

from pydantic import BaseModel, ConfigDict, Field

from haven.domain.enums import CouncilTaxBand, EpcBand, MainFuel, PropertyType
from haven.domain.evidence import Evidence


class RecurringCost(BaseModel):
    """A named recurring monthly cost (e.g. broadband, factor fee) in GBP."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    monthly_gbp: Evidence[float]


class Property(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str
    illustrative: bool = Field(
        default=False, description="True when this is a fictional example, not a real listing."
    )
    area: str | None = Field(default=None, description="Neighbourhood, never a house number.")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    rent_pcm_gbp: Evidence[float]
    bedrooms: Evidence[int]
    property_type: Evidence[PropertyType]
    floor_area_m2: Evidence[float]
    council_tax_band: Evidence[CouncilTaxBand]
    epc_rating: Evidence[EpcBand]
    main_fuel: Evidence[MainFuel]
    floor_level: Evidence[int] = Field(description="0 = ground floor.")
    has_lift: Evidence[bool]
    entrance_steps: Evidence[int] = Field(description="Number of steps at the entrance.")
    other_recurring_costs: list[RecurringCost] = Field(default_factory=list)
