import pytest
from pydantic import ValidationError

from haven.domain import (
    PROJECT_SCOPE_DISCLAIMER,
    BudgetComparison,
    CostBreakdown,
    CostKind,
    CostLine,
    Evidence,
    EvidenceQuality,
    Finding,
    FindingCategory,
    Likelihood,
    Origin,
    Outcome,
    Property,
    Report,
    Signal,
    SignalKind,
    Status,
)


def estimate(value: float | None) -> Evidence[float]:
    status = Status.insufficient if value is None else Status.estimated
    return Evidence[float](value=value, origin=Origin.estimate, source="engine", status=status)


# --- Evidence -------------------------------------------------------------------------


def test_evidence_known_value() -> None:
    ev = Evidence[int](value=3, origin=Origin.listing, source="listing", status=Status.known)
    assert ev.value == 3


def test_missing_value_requires_insufficient() -> None:
    with pytest.raises(ValidationError, match="insufficient"):
        Evidence[int](value=None, origin=Origin.listing, source="listing", status=Status.known)


def test_insufficient_requires_missing_value() -> None:
    with pytest.raises(ValidationError, match="null"):
        Evidence[int](value=3, origin=Origin.listing, source="listing", status=Status.insufficient)


def test_confidence_only_for_model_origin() -> None:
    with pytest.raises(ValidationError, match="confidence"):
        Evidence[bool](
            value=True,
            origin=Origin.listing,
            source="listing",
            status=Status.known,
            confidence=0.9,
        )
    ev = Evidence[bool](
        value=True, origin=Origin.model, source="m@1", status=Status.inferred, confidence=0.9
    )
    assert ev.confidence == 0.9


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_confidence_bounds(bad: float) -> None:
    with pytest.raises(ValidationError):
        Evidence[bool](
            value=True, origin=Origin.model, source="m@1", status=Status.inferred, confidence=bad
        )


def test_evidence_validates_value_type() -> None:
    with pytest.raises(ValidationError):
        Evidence[int](value="three", origin=Origin.user, source="renter", status=Status.known)


def test_evidence_json_round_trip() -> None:
    ev = Evidence[float](value=12.5, origin=Origin.estimate, source="engine", status="estimated")
    again = Evidence[float].model_validate_json(ev.model_dump_json())
    assert again == ev


# --- Cost -----------------------------------------------------------------------------


def test_cost_line_range_must_bracket_central() -> None:
    CostLine(
        kind=CostKind.energy, label="Energy", monthly_gbp=estimate(80), low_gbp=60, high_gbp=100
    )
    with pytest.raises(ValidationError, match="low <= central <= high"):
        CostLine(
            kind=CostKind.energy, label="Energy", monthly_gbp=estimate(80), low_gbp=90, high_gbp=100
        )
    with pytest.raises(ValidationError, match="both"):
        CostLine(kind=CostKind.energy, label="Energy", monthly_gbp=estimate(80), low_gbp=60)


def test_insufficient_cost_line_has_no_range() -> None:
    with pytest.raises(ValidationError, match="central"):
        CostLine(
            kind=CostKind.council_tax,
            label="Council tax",
            monthly_gbp=estimate(None),
            low_gbp=100,
            high_gbp=300,
        )


def test_budget_comparison_needs_budget_and_total() -> None:
    with pytest.raises(ValidationError, match="budget"):
        CostBreakdown(
            property_id="p1",
            lines=[],
            total_monthly_gbp=estimate(None),
            budget_monthly_gbp=1200,
            budget_comparison=BudgetComparison.within,
        )
    ok = CostBreakdown(
        property_id="p1",
        lines=[],
        total_monthly_gbp=estimate(1100),
        budget_monthly_gbp=1200,
        budget_comparison=BudgetComparison.within,
    )
    assert ok.budget_comparison is BudgetComparison.within


# --- Findings and signals -------------------------------------------------------------


@pytest.mark.parametrize("outcome", [Outcome.concern, Outcome.unknown])
def test_non_meeting_findings_need_next_step(outcome: Outcome) -> None:
    with pytest.raises(ValidationError, match="next_step"):
        Finding(
            id="f1",
            rule_id="step_free_entrance",
            category=FindingCategory.access,
            outcome=outcome,
            title="Entrance",
            reason="Listing does not say whether the entrance has steps.",
        )


def test_meeting_finding_without_next_step() -> None:
    f = Finding(
        id="f1",
        rule_id="budget_fit",
        category=FindingCategory.cost,
        outcome=Outcome.meets,
        title="Budget",
        reason="Estimated total is within the stated budget.",
    )
    assert f.next_step is None


def test_poor_evidence_forces_insufficient() -> None:
    with pytest.raises(ValidationError, match="insufficient_evidence"):
        Signal(
            id="s1",
            kind=SignalKind.possible_damp,
            likelihood=Likelihood.possible,
            evidence_quality=EvidenceQuality.poor,
            source="null@0",
        )
    s = Signal(
        id="s1",
        kind=SignalKind.possible_damp,
        likelihood=Likelihood.insufficient_evidence,
        evidence_quality=EvidenceQuality.poor,
        source="null@0",
    )
    assert s.confidence is None


def test_insufficient_signal_has_no_confidence() -> None:
    with pytest.raises(ValidationError, match="confidence"):
        Signal(
            id="s1",
            kind=SignalKind.entrance_step,
            likelihood=Likelihood.insufficient_evidence,
            evidence_quality=EvidenceQuality.good,
            confidence=0.4,
            source="null@0",
        )


# --- Property and report --------------------------------------------------------------


def test_property_keeps_provenance_per_field(prop: Property) -> None:
    assert prop.council_tax_band.status is Status.insufficient
    assert prop.council_tax_band.value is None
    assert prop.epc_rating.origin is Origin.listing


def test_report_disclaimer_defaults_to_project_scope(report: Report) -> None:
    assert report.disclaimer == PROJECT_SCOPE_DISCLAIMER
    assert "not a legal, safety, accessibility or compliance certification" in report.disclaimer


def test_report_json_round_trip(report: Report) -> None:
    again = Report.model_validate_json(report.model_dump_json())
    assert again == report


def test_models_reject_unknown_fields(report: Report) -> None:
    data = report.model_dump()
    data["overall_score"] = 7
    with pytest.raises(ValidationError):
        Report.model_validate(data)
