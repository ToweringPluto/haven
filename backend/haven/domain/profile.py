"""Renter profile.

Everything here is stated by the renter (origin ``user``), so fields are plain
values rather than ``Evidence``. ``None`` means "not stated", never "no limit".
"""

from pydantic import BaseModel, ConfigDict, Field

from haven.domain.enums import Priority
from haven.domain.property import RecurringCost


class AccessRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wheelchair_user: bool = False
    step_free_entrance_required: bool = False
    lift_required_above_floor: int | None = Field(
        default=None, ge=0, description="A lift is needed for floors above this level."
    )
    max_walk_to_stop_m: int | None = Field(default=None, gt=0)


class Destination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    max_travel_minutes: int | None = Field(default=None, gt=0)


class RenterProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(description="Display name for the profile, e.g. a persona name.")
    monthly_budget_gbp: float | None = Field(default=None, gt=0)
    priorities: list[Priority] = Field(default_factory=list)
    access: AccessRequirements = Field(default_factory=AccessRequirements)
    destinations: list[Destination] = Field(default_factory=list)
    other_recurring_costs: list[RecurringCost] = Field(default_factory=list)
