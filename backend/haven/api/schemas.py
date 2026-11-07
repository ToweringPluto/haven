"""API envelopes that are not domain objects: request bodies, list wrappers, enum metadata
and RFC 9457 problem details."""

from pydantic import BaseModel, ConfigDict, Field

from haven.domain import (
    AccessRequirements,
    CouncilTaxBand,
    Destination,
    EpcBand,
    Evidence,
    MainFuel,
    Priority,
    Property,
    PropertyType,
    RecurringCost,
    RenterProfile,
)


class PropertyList(BaseModel):
    """A list wrapper, so pagination fields can be added later without breaking clients."""

    model_config = ConfigDict(extra="forbid")

    items: list[Property]


class ProfileList(BaseModel):
    """A list wrapper, so pagination fields can be added later without breaking clients."""

    model_config = ConfigDict(extra="forbid")

    items: list[RenterProfile]


class ProfileInput(BaseModel):
    """A renter profile as submitted by a client. The server assigns the id."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(description="Display name for the profile, e.g. a persona name.")
    monthly_budget_gbp: float | None = Field(default=None, gt=0)
    priorities: list[Priority] = Field(default_factory=list)
    access: AccessRequirements = Field(default_factory=AccessRequirements)
    destinations: list[Destination] = Field(default_factory=list)
    other_recurring_costs: list[RecurringCost] = Field(default_factory=list)


class PropertyInput(BaseModel):
    """A property as submitted by a client. The server assigns the id.

    Every fact carries its own provenance; a value the client doesn't have is sent as
    ``{"value": null, "status": "insufficient", ...}``, never left out or defaulted.
    """

    model_config = ConfigDict(extra="forbid")

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


class CostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = Field(
        default=None,
        description="Profile whose budget and other costs to use. Without it, the budget "
        "comparison is 'unknown'.",
    )


class SuitabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1, description="Profile whose requirements to check.")


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    property_id: str = Field(min_length=1)
    upload_ids: list[str] = Field(
        default_factory=list, description="Uploaded evidence to include in the report."
    )


class EnumOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str = Field(description="Human-readable label to show instead of the raw value.")


class EnumCatalog(BaseModel):
    """Every enum used in the contract, with display labels."""

    model_config = ConfigDict(extra="forbid")

    enums: dict[str, list[EnumOption]]


class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loc: list[str | int] = Field(description="Path to the offending field.")
    msg: str
    type: str


class ProblemDetail(BaseModel):
    """RFC 9457 problem details (`application/problem+json`)."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(default="about:blank", description="URI identifying the problem type.")
    title: str
    status: int = Field(ge=400, le=599)
    detail: str | None = None
    instance: str | None = None
    errors: list[FieldError] | None = Field(
        default=None, description="Field-level validation errors (422 only)."
    )
