"""Monthly cost breakdown (GBP). Estimates carry a low/high range."""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.domain.enums import BudgetComparison, CostKind, RentComparison
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


class RentContext(BaseModel):
    """The listing's rent next to local rent statistics and the Local Housing Allowance.

    Context for the rent, never a valuation of the property. Absent (``null`` on the
    breakdown) for studios and 5+ bedroom homes, which the statistics don't publish.
    """

    model_config = ConfigDict(extra="forbid")

    bedrooms: int = Field(ge=1, le=4)
    area: str = Field(description="The area the figures describe (wider than Edinburgh).")
    lower_quartile_gbp_pcm: float = Field(gt=0)
    median_gbp_pcm: float = Field(gt=0)
    upper_quartile_gbp_pcm: float = Field(gt=0)
    statistics_year: int = Field(description="Statistics year, running to the end of September.")
    statistics_source: str = Field(min_length=1)
    statistics_as_of: date
    lha_monthly_gbp: float | None = Field(
        default=None, gt=0, description="Monthly Local Housing Allowance rate for the size."
    )
    lha_source: str | None = None
    lha_as_of: date | None = None
    rent_vs_median: RentComparison | None = Field(
        default=None, description="Null when the listing's rent isn't known."
    )
    rent_vs_lha: RentComparison | None = Field(
        default=None, description="Null when the rent or the LHA rate isn't known."
    )
    caveats: list[str] = Field(description="Known limits. Show every one.")


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
    rent_context: RentContext | None = Field(
        default=None,
        description="Local rent statistics and housing allowance for comparison, when "
        "available for the property's size.",
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        _check_range(self.total_low_gbp, self.total_monthly_gbp.value, self.total_high_gbp)
        if self.budget_comparison is not BudgetComparison.unknown and (
            self.budget_monthly_gbp is None or self.total_monthly_gbp.value is None
        ):
            raise ValueError("budget comparison needs both a budget and a total")
        return self
