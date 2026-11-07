"""``Evidence[T]``: a value with its provenance and uncertainty attached."""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.domain.enums import Origin, Status


class Evidence[T](BaseModel):
    """A single fact plus where it came from and how far it can be trusted.

    Rules enforced here:

    * ``value is None`` if and only if ``status == insufficient``. A missing value
      is never silently replaced by a default.
    * ``confidence`` may only be set when ``origin == model`` and lies in [0, 1].
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: T | None = Field(description="The value, or null when evidence is insufficient.")
    origin: Origin = Field(description="Where the value came from.")
    source: str = Field(min_length=1, description="Named source, e.g. a dataset or 'listing'.")
    as_of: date | None = Field(default=None, description="Date the source refers to or was read.")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated model confidence; only allowed when origin is 'model'.",
    )
    status: Status
    note: str | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.value is None and self.status is not Status.insufficient:
            raise ValueError("a missing value must have status 'insufficient'")
        if self.value is not None and self.status is Status.insufficient:
            raise ValueError("status 'insufficient' requires value to be null")
        if self.confidence is not None and self.origin is not Origin.model:
            raise ValueError("confidence is only allowed when origin is 'model'")
        return self
