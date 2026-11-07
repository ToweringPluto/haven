"""API envelopes that are not domain objects: list wrappers and RFC 9457 problem details."""

from pydantic import BaseModel, ConfigDict, Field

from haven.domain import Property


class PropertyList(BaseModel):
    """A list wrapper, so pagination fields can be added later without breaking clients."""

    model_config = ConfigDict(extra="forbid")

    items: list[Property]


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
