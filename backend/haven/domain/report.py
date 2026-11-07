"""The assembled report. It deliberately has no overall score."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from haven.domain.cost import CostBreakdown
from haven.domain.findings import Finding, Signal
from haven.domain.profile import RenterProfile
from haven.domain.property import Property

PROJECT_SCOPE_DISCLAIMER = (
    "Haven is a prototype and decision-support tool. It is not a legal, safety, "
    "accessibility or compliance certification system. Its assessments are indicative "
    "and should be checked against the property in person and with appropriate "
    "professional advice."
)


class ReportSentence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    cites: list[str] = Field(
        default_factory=list, description="Ids of the findings/signals this sentence relies on."
    )


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    sentences: list[ReportSentence] = Field(default_factory=list)


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    created_at: datetime
    illustrative: bool = Field(
        default=False, description="True when the report is an illustrative example."
    )
    profile: RenterProfile
    property: Property
    cost: CostBreakdown | None = None
    findings: list[Finding] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    disclaimer: str = PROJECT_SCOPE_DISCLAIMER
