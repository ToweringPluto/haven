"""API envelopes that are not domain objects: request bodies, list wrappers, enum metadata
and RFC 9457 problem details."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from haven.domain import (
    AccessRequirements,
    CouncilTaxBand,
    Destination,
    EpcBand,
    Evidence,
    EvidenceQuality,
    MainFuel,
    Priority,
    Property,
    PropertyType,
    RecurringCost,
    RenterProfile,
    Signal,
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


class DataSource(BaseModel):
    """One dataset from the registry (``data/datasets.yml``), for the "Data and limits" page."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable dataset id, e.g. 'private_rents'.")
    name: str
    url: str = Field(description="Link to the source; show it as a link.")
    licence_note: str = Field(description="Licence and attribution. Show it verbatim.")
    as_of: date = Field(description="Date the figures describe (period, edition or snapshot).")
    caveats: list[str] = Field(description="Known limits. Show every one.")


class DataSourceList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DataSource]


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


# --- Signed-in features -------------------------------------------------------------------


class CurrentUser(BaseModel):
    """The signed-in user, from verified access-token claims. Never includes the token."""

    model_config = ConfigDict(extra="forbid")

    sub: str = Field(min_length=1, description="Auth0 user id (the token's `sub` claim).")
    email: str | None = Field(
        default=None, description="Email, when the token carries the configured email claim."
    )


class PhotoScreen(BaseModel):
    """Screening of one photo. The image is processed in memory and never stored, so there is
    no upload id and nothing to delete."""

    model_config = ConfigDict(extra="forbid")

    evidence_quality: EvidenceQuality | None = Field(
        description="Image quality gate result; null when the screener couldn't assess it."
    )
    signals: list[Signal] = Field(
        description="Possible issues to inspect, never diagnoses. May be empty."
    )


class ReadAloudRequest(BaseModel):
    """Text to turn into speech. The maximum length is set by HAVEN_READ_ALOUD_MAX_CHARS."""

    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Plain text to read aloud."
    )
