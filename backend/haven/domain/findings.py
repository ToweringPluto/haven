"""Rule findings and screening signals."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.domain.enums import EvidenceQuality, FindingCategory, Likelihood, Outcome, SignalKind
from haven.domain.evidence import Evidence

type FactValue = str | int | float | bool


class CitedFact(BaseModel):
    """A named input a finding relied on, with its provenance."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    evidence: Evidence[FactValue]


class Finding(BaseModel):
    """Result of one transparent rule. Concerns and unknowns always say what to check next."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    category: FindingCategory
    outcome: Outcome
    title: str
    reason: str
    facts: list[CitedFact] = Field(default_factory=list)
    next_step: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.outcome is not Outcome.meets and not self.next_step:
            raise ValueError("findings with outcome 'concern' or 'unknown' need a next_step")
        return self


class Signal(BaseModel):
    """A screening signal from uploaded evidence: a possibility to inspect, not a diagnosis."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: SignalKind
    likelihood: Likelihood
    evidence_quality: EvidenceQuality
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Calibrated confidence, when available."
    )
    upload_id: str | None = None
    source: str = Field(min_length=1, description="Screener name and version.")
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.evidence_quality is EvidenceQuality.poor and (
            self.likelihood is not Likelihood.insufficient_evidence
        ):
            raise ValueError("poor evidence quality must yield 'insufficient_evidence'")
        if self.likelihood is Likelihood.insufficient_evidence and self.confidence is not None:
            raise ValueError("'insufficient_evidence' signals carry no confidence")
        return self
