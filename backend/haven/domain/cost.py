"""Monthly cost breakdown (GBP). Estimates carry a low/high range."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.domain.enums import BudgetComparison, CostKind
from haven.domain.evidence import Evidence


def _check_range(low: float | None, central: float | None, high: float | None) -> None:
    if (low is None) != (high is None):
        raise ValueError("low and high must both be set or both be null")
    if low is not None and high is not None:
        if central is None:
            raise ValueError("a range requires a central value")
        if not low <= central <= high:
            raise ValueError("expected low <= central <= high")


class CostLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CostKind
    label: str
    monthly_gbp: Evidence[float] = Field(description="Central monthly estimate.")
    low_gbp: float | None = None
    high_gbp: float | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        _check_range(self.low_gbp, self.monthly_gbp.value, self.high_gbp)
        return self


class CostBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: str
    profile_id: str | None = None
    lines: list[CostLine]
    total_monthly_gbp: Evidence[float] = Field(
        description="Central total; insufficient when any line is insufficient."
    )
    total_low_gbp: float | None = None
    total_high_gbp: float | None = None
    budget_monthly_gbp: float | None = None
    budget_comparison: BudgetComparison

    @model_validator(mode="after")
    def _check(self) -> Self:
        _check_range(self.total_low_gbp, self.total_monthly_gbp.value, self.total_high_gbp)
        if self.budget_comparison is not BudgetComparison.unknown and (
            self.budget_monthly_gbp is None or self.total_monthly_gbp.value is None
        ):
            raise ValueError("budget comparison needs both a budget and a total")
        return self
