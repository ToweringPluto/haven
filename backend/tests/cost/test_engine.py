"""Tests for ``haven.cost.estimate_monthly_cost`` against the committed reference data."""

from datetime import date
from typing import Any

import pytest

from haven.cost import CostReferences, estimate_monthly_cost, load_cost_references
from haven.domain import (
    BudgetComparison,
    CostBreakdown,
    CostKind,
    CostLine,
    CouncilTaxBand,
    EpcBand,
    MainFuel,
    Property,
    PropertyType,
    RenterProfile,
    Status,
)

ON = date(2026, 11, 7)  # inside the 2026/27 council tax year and the Oct-Dec 2026 price cap
HEATING = "Estimated heating and hot water"
ELECTRICITY = "Estimated electricity (lighting, appliances, cooking)"


def ev(value: Any, origin: str = "listing", status: str = "known") -> dict[str, Any]:
    return {
        "value": value,
        "origin": origin,
        "source": "test listing",
        "as_of": "2026-11-01",
        "status": "insufficient" if value is None else status,
    }


def make_property(**overrides: Any) -> Property:
    data: dict[str, Any] = {
        "id": "test-prop",
        "title": "Test flat",
        "rent_pcm_gbp": ev(900.0),
        "bedrooms": ev(2),
        "property_type": ev("flat"),
        "floor_area_m2": ev(60.0),
        "council_tax_band": ev("C"),
        "epc_rating": ev("D"),
        "main_fuel": ev("mains_gas"),
        "floor_level": ev(1),
        "has_lift": ev(False),
        "entrance_steps": ev(0),
    }
    data.update(overrides)
    return Property.model_validate(data)


def make_profile(budget: float | None = 1500.0, **overrides: Any) -> RenterProfile:
    data: dict[str, Any] = {"id": "test-profile", "label": "Test renter"}
    if budget is not None:
        data["monthly_budget_gbp"] = budget
    data.update(overrides)
    return RenterProfile.model_validate(data)


@pytest.fixture(scope="module")
def refs() -> CostReferences:
    return load_cost_references()


def line(cost: CostBreakdown, label_start: str) -> CostLine:
    (found,) = [ln for ln in cost.lines if ln.label.startswith(label_start)]
    return found


def monthly(annual_pence: float) -> float:
    return round(annual_pence / 100 / 12, 2)


# --- all inputs present ---------------------------------------------------------------


def test_all_inputs_present(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(make_property(), make_profile(), on=ON, references=refs)

    assert [ln.kind for ln in cost.lines] == [
        CostKind.rent,
        CostKind.council_tax,
        CostKind.energy,
        CostKind.energy,
    ]
    assert cost.property_id == "test-prop"
    assert cost.profile_id == "test-profile"

    rent = line(cost, "Rent")
    assert rent.monthly_gbp.value == 900.0
    assert rent.monthly_gbp.status is Status.known

    ct = line(cost, "Council tax")
    year = refs.council_tax.years["2026/27"]
    assert ct.label == "Council tax, water and waste water (band C)"
    assert ct.monthly_gbp.value == round(year.bands[CouncilTaxBand.C].total_gbp / 12, 2)
    assert ct.monthly_gbp.status is Status.known
    assert ct.low_gbp is None and ct.high_gbp is None

    match = refs.energy_model.lookup(EpcBand.D, PropertyType.flat, MainFuel.mains_gas)
    assert match is not None
    gas = refs.energy_rates.gas
    standing = gas.standing_charge_p_per_day * 365
    heat = line(cost, HEATING)
    d = match.distribution
    assert heat.monthly_gbp.value == monthly(60 * d.median * gas.unit_rate_p_per_kwh + standing)
    assert heat.low_gbp == monthly(60 * d.q1 * gas.unit_rate_p_per_kwh + standing)
    assert heat.high_gbp == monthly(60 * d.q3 * gas.unit_rate_p_per_kwh + standing)
    assert heat.monthly_gbp.status is Status.estimated
    assert heat.monthly_gbp.origin == "estimate"
    assert "system losses" in (heat.monthly_gbp.note or "")

    elec = line(cost, ELECTRICITY)
    rates = refs.energy_rates.electricity
    levels = refs.electricity_use.electricity
    sc = rates.standing_charge_p_per_day * 365
    assert elec.monthly_gbp.value == monthly(
        levels.medium_kwh_per_year * rates.unit_rate_p_per_kwh + sc
    )
    assert elec.low_gbp == monthly(levels.low_kwh_per_year * rates.unit_rate_p_per_kwh + sc)
    assert elec.high_gbp == monthly(levels.high_kwh_per_year * rates.unit_rate_p_per_kwh + sc)
    assert "spread between households" in (elec.monthly_gbp.note or "")

    values = [ln.monthly_gbp.value for ln in cost.lines]
    assert all(v is not None for v in values)
    total = cost.total_monthly_gbp
    assert total.value == pytest.approx(sum(v for v in values if v is not None), abs=0.011)
    assert total.status is Status.estimated
    assert cost.total_low_gbp is not None and cost.total_high_gbp is not None
    assert cost.total_low_gbp < total.value < cost.total_high_gbp
    assert cost.budget_monthly_gbp == 1500.0
    assert cost.budget_comparison is BudgetComparison.within


def test_council_tax_anchor_2025_26(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(
        make_property(council_tax_band=ev("A")), None, on=date(2025, 6, 1), references=refs
    )
    # Sanity anchor from the council's PDF: 1042.34 + 185.28 + 214.98 = 1442.60 a year.
    assert line(cost, "Council tax").monthly_gbp.value == round(1442.60 / 12, 2)


# --- missing inputs never become 0 ----------------------------------------------------


def test_missing_council_tax_band(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(
        make_property(council_tax_band=ev(None)), make_profile(), on=ON, references=refs
    )
    ct = line(cost, "Council tax")
    assert ct.label == "Council tax (band unknown)"
    assert ct.monthly_gbp.value is None
    assert ct.monthly_gbp.status is Status.insufficient
    year = refs.council_tax.years["2026/27"]
    note = ct.monthly_gbp.note or ""
    assert f"£{year.bands[CouncilTaxBand.A].total_gbp / 12:,.2f} (band A)" in note
    assert f"£{year.bands[CouncilTaxBand.H].total_gbp / 12:,.2f} (band H)" in note

    assert cost.total_monthly_gbp.value is None
    assert cost.total_monthly_gbp.status is Status.insufficient
    assert "Council tax (band unknown)" in (cost.total_monthly_gbp.note or "")
    assert cost.total_low_gbp is None and cost.total_high_gbp is None
    assert cost.budget_monthly_gbp == 1500.0
    assert cost.budget_comparison is BudgetComparison.unknown


@pytest.mark.parametrize(
    ("field", "missing_name"),
    [("epc_rating", "EPC rating"), ("floor_area_m2", "floor area"), ("main_fuel", "main heating")],
)
def test_missing_energy_input(refs: CostReferences, field: str, missing_name: str) -> None:
    cost = estimate_monthly_cost(
        make_property(**{field: ev(None)}), make_profile(), on=ON, references=refs
    )
    heat = line(cost, HEATING)
    assert heat.monthly_gbp.value is None
    assert heat.monthly_gbp.status is Status.insufficient
    assert heat.low_gbp is None and heat.high_gbp is None
    assert missing_name in (heat.monthly_gbp.note or "")
    # Electricity doesn't depend on these inputs and is still estimated.
    assert line(cost, ELECTRICITY).monthly_gbp.status is Status.estimated
    assert cost.total_monthly_gbp.value is None
    assert cost.budget_comparison is BudgetComparison.unknown


def test_missing_rent(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(
        make_property(rent_pcm_gbp=ev(None)), make_profile(), on=ON, references=refs
    )
    assert line(cost, "Rent").label == "Rent (not stated)"
    assert cost.total_monthly_gbp.value is None


def test_unusable_floor_area(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(make_property(floor_area_m2=ev(0.0)), None, on=ON, references=refs)
    assert line(cost, HEATING).monthly_gbp.value is None


def test_other_heating_fuel_is_insufficient(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(make_property(main_fuel=ev("other")), None, on=ON, references=refs)
    heat = line(cost, HEATING)
    assert heat.monthly_gbp.value is None
    assert "community heating" in (heat.monthly_gbp.note or "")


def test_dates_outside_reference_data(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(make_property(), make_profile(), on=date(2027, 6, 1))
    for label in ("Council tax", HEATING, ELECTRICITY):
        ln = line(cost, label)
        assert ln.monthly_gbp.value is None, label
        assert "2027-06-01" in (ln.monthly_gbp.note or "")
    assert cost.total_monthly_gbp.value is None
    assert cost.budget_comparison is BudgetComparison.unknown


def test_electricity_figures_not_in_force(refs: CostReferences) -> None:
    later = refs.electricity_use.model_copy(update={"valid_from": date(2026, 12, 1)})
    patched = CostReferences(
        refs.council_tax, refs.energy_rates, refs.energy_model, electricity_use=later
    )
    cost = estimate_monthly_cost(make_property(), None, on=ON, references=patched)
    elec = line(cost, ELECTRICITY)
    assert elec.monthly_gbp.value is None
    assert "2026-12-01" in (elec.monthly_gbp.note or "")


def test_heat_demand_group_fallback_and_missing_band(refs: CostReferences) -> None:
    model = refs.energy_model.model_copy(
        update={
            "groups": [],
            "band_groups": [g for g in refs.energy_model.band_groups if g.epc_band != "G"],
        }
    )
    patched = CostReferences(refs.council_tax, refs.energy_rates, model, refs.electricity_use)

    cost = estimate_monthly_cost(make_property(), None, on=ON, references=patched)
    heat = line(cost, HEATING)
    assert heat.monthly_gbp.status is Status.estimated
    assert "all property types and fuels" in (heat.monthly_gbp.note or "")

    cost = estimate_monthly_cost(make_property(epc_rating=ev("G")), None, on=ON, references=patched)
    heat = line(cost, HEATING)
    assert heat.monthly_gbp.value is None
    assert "band G" in (heat.monthly_gbp.note or "")


# --- fuel-specific behaviour ----------------------------------------------------------


def test_electric_heating(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(
        make_property(main_fuel=ev("electricity")), None, on=ON, references=refs
    )
    heat = line(cost, HEATING)
    match = refs.energy_model.lookup(EpcBand.D, PropertyType.flat, MainFuel.electricity)
    assert match is not None
    rate = refs.energy_rates.electricity.unit_rate_p_per_kwh
    # No standing charge on the heating line: it's counted once, on the electricity line.
    assert heat.monthly_gbp.value == monthly(60 * match.distribution.median * rate)
    assert "double-count" in (line(cost, ELECTRICITY).monthly_gbp.note or "")


def test_band_status_carried_onto_council_tax_line(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(
        make_property(council_tax_band=ev("B", origin="model", status="inferred")),
        None,
        on=ON,
        references=refs,
    )
    ct = line(cost, "Council tax")
    assert ct.monthly_gbp.status is Status.inferred
    assert "inferred" in (ct.monthly_gbp.note or "")
    assert cost.total_monthly_gbp.status is Status.estimated


# --- other costs + budget -------------------------------------------------------------


def test_other_recurring_costs_from_property_and_profile(refs: CostReferences) -> None:
    prop = make_property(other_recurring_costs=[{"label": "Factor fee", "monthly_gbp": ev(25.0)}])
    profile = make_profile(
        other_recurring_costs=[{"label": "Broadband", "monthly_gbp": ev(30.0, origin="user")}]
    )
    cost = estimate_monthly_cost(prop, profile, on=ON, references=refs)
    others = [ln for ln in cost.lines if ln.kind is CostKind.other]
    assert [(ln.label, ln.monthly_gbp.value, ln.monthly_gbp.origin) for ln in others] == [
        ("Factor fee", 25.0, "listing"),
        ("Broadband", 30.0, "user"),
    ]
    base = estimate_monthly_cost(make_property(), make_profile(), on=ON, references=refs)
    assert cost.total_monthly_gbp.value is not None and base.total_monthly_gbp.value is not None
    assert cost.total_monthly_gbp.value == pytest.approx(base.total_monthly_gbp.value + 55.0)


def test_unknown_other_cost_makes_total_insufficient(refs: CostReferences) -> None:
    prop = make_property(other_recurring_costs=[{"label": "Factor fee", "monthly_gbp": ev(None)}])
    cost = estimate_monthly_cost(prop, make_profile(), on=ON, references=refs)
    assert cost.total_monthly_gbp.value is None
    assert "Factor fee" in (cost.total_monthly_gbp.note or "")


def test_over_budget(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(make_property(), make_profile(budget=900.0), on=ON)
    assert cost.budget_comparison is BudgetComparison.over
    assert cost.total_monthly_gbp.value is not None
    assert cost.total_monthly_gbp.value > 900.0


def test_under_budget(refs: CostReferences) -> None:
    cost = estimate_monthly_cost(make_property(), make_profile(budget=5000.0), on=ON)
    assert cost.budget_comparison is BudgetComparison.within
    assert "could go either way" not in (cost.total_monthly_gbp.note or "")


def test_budget_inside_range_is_flagged(refs: CostReferences) -> None:
    base = estimate_monthly_cost(make_property(), None, on=ON, references=refs)
    assert base.total_monthly_gbp.value is not None and base.total_high_gbp is not None
    budget = (base.total_monthly_gbp.value + base.total_high_gbp) / 2
    cost = estimate_monthly_cost(make_property(), make_profile(budget), on=ON, references=refs)
    assert cost.budget_comparison is BudgetComparison.within
    assert "could go either way" in (cost.total_monthly_gbp.note or "")


@pytest.mark.parametrize("profile", [None, make_profile(budget=None)])
def test_no_budget_means_unknown(refs: CostReferences, profile: RenterProfile | None) -> None:
    cost = estimate_monthly_cost(make_property(), profile, on=ON, references=refs)
    assert cost.total_monthly_gbp.value is not None
    assert cost.budget_monthly_gbp is None
    assert cost.budget_comparison is BudgetComparison.unknown
    assert cost.profile_id == (None if profile is None else profile.id)


def test_defaults_to_today_and_committed_references() -> None:
    cost = estimate_monthly_cost(make_property(), None)
    assert len(cost.lines) == 4


# --- provenance -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "prop",
    [make_property(), make_property(council_tax_band=ev(None), epc_rating=ev(None))],
    ids=["complete", "missing-band-and-epc"],
)
def test_reference_provenance_on_every_line(refs: CostReferences, prop: Property) -> None:
    cost = estimate_monthly_cost(prop, make_profile(), on=ON, references=refs)
    for ln in cost.lines:
        assert ln.monthly_gbp.source, ln.label
        assert ln.monthly_gbp.note or ln.kind is CostKind.rent, ln.label

    ct = line(cost, "Council tax").monthly_gbp
    assert refs.council_tax.years["2026/27"].source_url in ct.source
    assert ct.origin == "public_data"
    assert ct.as_of == refs.council_tax.meta.retrieved

    heat = line(cost, HEATING).monthly_gbp
    assert refs.energy_model.meta.source_url in heat.source
    assert heat.as_of is not None

    elec = line(cost, ELECTRICITY).monthly_gbp
    assert refs.electricity_use.source_url in elec.source
    assert refs.energy_rates.electricity.source_url in elec.source
    assert elec.as_of is not None

    if prop.epc_rating.value is not None:
        assert refs.energy_rates.gas.source_url in heat.source
        assert "2026-10-01 to 2026-12-31" in (heat.note or "")


def test_rent_evidence_passed_through_unchanged(refs: CostReferences) -> None:
    prop = make_property()
    cost = estimate_monthly_cost(prop, None, on=ON, references=refs)
    assert line(cost, "Rent").monthly_gbp == prop.rent_pcm_gbp
