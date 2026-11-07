"""Suitability assessment: the rule findings for one property and one renter profile."""

from pydantic import BaseModel, ConfigDict, Field

from haven.domain.findings import Finding


class SuitabilityAssessment(BaseModel):
    """Per-requirement indicators. There is deliberately no aggregate result."""

    model_config = ConfigDict(extra="forbid")

    property_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    findings: list[Finding] = Field(default_factory=list)
