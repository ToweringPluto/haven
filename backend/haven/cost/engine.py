"""Deterministic monthly cost estimate for one property and (optionally) one renter.

``estimate_monthly_cost`` builds a :class:`~haven.domain.CostBreakdown` from:

* **rent**: the property's rent evidence, passed through unchanged;
* **council tax**: the City of Edinburgh Council's annual charge for the band (council tax +
  Scottish Water water and waste water, billed together) / 12;
* **energy**, as two lines:

  - *heating and hot water*: floor area × the Edinburgh EPC median heat demand (kWh/m²/year)
    for the property's group, priced at the Ofgem price cap unit rate for its heating fuel
    (plus the gas standing charge for gas-heated homes). The interquartile range gives
    low/high. This is **heat demand, not fuel bought**: boiler/system losses aren't included,
    so for most systems it is an underestimate;
  - *electricity*: Ofgem's typical domestic consumption values (median, with lower/upper
    quartile as low/high) priced at the electricity cap unit rate plus standing charge;

* **other recurring costs** listed on the property or stated in the renter profile.

Missing inputs never become 0: a line that can't be calculated is ``insufficient``, and then
the total is ``insufficient`` too. Every line names its sources and the date they were read.
"""

from collections.abc import Sequence
from datetime import date

from haven.cost.references import CostReferences, load_cost_references
from haven.domain import (
    BudgetComparison,
    CostBreakdown,
    CostKind,
    CostLine,
    Evidence,
    MainFuel,
    Origin,
    Property,
    RenterProfile,
    Status,
)
from haven.reference import CouncilTaxYear, FuelRates

DAYS_PER_YEAR = 365
MONTHS_PER_YEAR = 12

ENGINE_SOURCE = "Haven cost engine: sum of the cost lines"


def _gbp(value: float) -> float:
    return round(value, 2)


def _money(value: float) -> str:
    return f"£{value:,.2f}"


def _annual_pence_to_monthly_gbp(pence: float) -> float:
    return pence / 100 / MONTHS_PER_YEAR


def _line(
    kind: CostKind,
    label: str,
    *,
    value: float | None,
    origin: Origin,
    source: str,
    as_of: date | None,
    status: Status,
    note: str,
    low: float | None = None,
    high: float | None = None,
) -> CostLine:
    evidence = Evidence[float](
        value=None if value is None else _gbp(value),
        origin=origin,
        source=source,
        as_of=as_of,
        status=Status.insufficient if value is None else status,
        note=note,
    )
    return CostLine(
        kind=kind,
        label=label,
        monthly_gbp=evidence,
        low_gbp=None if low is None or value is None else _gbp(low),
        high_gbp=None if high is None or value is None else _gbp(high),
    )


# --- rent -----------------------------------------------------------------------------


def _rent_line(prop: Property) -> CostLine:
    rent = prop.rent_pcm_gbp
    label = "Rent" if rent.value is not None else "Rent (not stated)"
    return CostLine(kind=CostKind.rent, label=label, monthly_gbp=rent)


# --- council tax ----------------------------------------------------------------------


def _council_tax_year(refs: CostReferences, on: date) -> tuple[str, CouncilTaxYear] | None:
    for key, year in refs.council_tax.years.items():
        if year.valid_from <= on <= year.valid_to:
            return key, year
    return None


def _council_tax_line(prop: Property, refs: CostReferences, on: date) -> CostLine:
    meta = refs.council_tax.meta
    band = prop.council_tax_band
    found = _council_tax_year(refs, on)
    if found is None:
        return _line(
            CostKind.council_tax,
            "Council tax",
            value=None,
            origin=Origin.public_data,
            source=f"City of Edinburgh Council, Council Tax charges ({meta.source_url})",
            as_of=meta.retrieved,
            status=Status.insufficient,
            note=f"No Edinburgh council tax charges are on file for {on.isoformat()}, so this "
            "line can't be calculated.",
        )
    key, year = found
    source = f"City of Edinburgh Council, Council Tax charges {key} ({year.source_url})"
    if band.value is None:
        totals = [charges.total_gbp for charges in year.bands.values()]
        low = _money(min(totals) / MONTHS_PER_YEAR)
        high = _money(max(totals) / MONTHS_PER_YEAR)
        return _line(
            CostKind.council_tax,
            "Council tax (band unknown)",
            value=None,
            origin=Origin.public_data,
            source=source,
            as_of=meta.retrieved,
            status=Status.insufficient,
            note="Council tax band unknown, so this line can't be calculated. "
            f"In {key} it would be between {low} (band A) and {high} (band H) a month, "
            "including water and waste water. Ask the landlord for the band.",
        )
    charges = year.bands[band.value]
    note = (
        f"Annual {key} charge for band {band.value.value} / 12: council tax "
        f"{_money(charges.council_tax_gbp)} + water {_money(charges.water_gbp)} + waste water "
        f"{_money(charges.waste_water_gbp)} = {_money(charges.total_gbp)} a year. Full charge "
        "before any discount or exemption (e.g. single-person discount, student exemption), "
        "which aren't modelled."
    )
    status = Status.known
    if band.status is not Status.known:
        status = band.status
        note += f" The band itself is {band.status.value} (source: {band.source})."
    return _line(
        CostKind.council_tax,
        f"Council tax, water and waste water (band {band.value.value})",
        value=charges.total_gbp / MONTHS_PER_YEAR,
        origin=Origin.public_data,
        source=source,
        as_of=meta.retrieved,
        status=status,
        note=note,
    )


# --- energy ---------------------------------------------------------------------------


def _rates_source(refs: CostReferences, fuel: str, rates: FuelRates) -> str:
    r = refs.energy_rates
    return (
        f"Ofgem energy price cap, {r.region}, Direct Debit, {r.valid_from.isoformat()} to "
        f"{r.valid_to.isoformat()}, {fuel} ({rates.source_url})"
    )


def _rates_period_note(refs: CostReferences) -> str:
    r = refs.energy_rates
    return (
        f"Priced for a whole year at the {r.valid_from.isoformat()} to {r.valid_to.isoformat()} "
        "price cap rates (default tariff, Direct Debit); rates change every quarter and your "
        "tariff may differ."
    )


def _rates_unavailable(refs: CostReferences, label: str, on: date) -> CostLine:
    r = refs.energy_rates
    return _line(
        CostKind.energy,
        label,
        value=None,
        origin=Origin.estimate,
        source=f"Ofgem energy price cap ({r.meta.source_url})",
        as_of=r.meta.retrieved,
        status=Status.insufficient,
        note=f"No energy price cap rates are on file for {on.isoformat()} (rates on file cover "
        f"{r.valid_from.isoformat()} to {r.valid_to.isoformat()}), so this line can't be "
        "estimated.",
    )


def _heating_line(prop: Property, refs: CostReferences, on: date) -> CostLine:
    label = "Estimated heating and hot water"
    if not refs.energy_rates.covers(on):
        return _rates_unavailable(refs, label, on)
    model = refs.energy_model
    model_source = (
        f"Scottish domestic EPC register, {model.local_authority}, {model.dataset_release} "
        f"({model.meta.source_url})"
    )
    as_of = min(model.meta.retrieved, refs.energy_rates.meta.retrieved)

    def insufficient(note: str) -> CostLine:
        return _line(
            CostKind.energy,
            label,
            value=None,
            origin=Origin.estimate,
            source=model_source,
            as_of=as_of,
            status=Status.insufficient,
            note=note,
        )

    epc = prop.epc_rating.value
    area = prop.floor_area_m2.value
    fuel = prop.main_fuel.value
    missing = [
        name
        for name, value in (
            ("EPC rating", epc),
            ("floor area", area),
            ("main heating fuel", fuel),
        )
        if value is None
    ]
    if missing:
        return insufficient(
            f"Can't estimate heating and hot water without the {', '.join(missing)}. "
            "Ask the landlord for the EPC certificate."
        )
    assert epc is not None and area is not None and fuel is not None
    if area <= 0:
        return insufficient("The stated floor area isn't usable, so this line can't be estimated.")
    if fuel is MainFuel.other:
        return insufficient(
            "There is no reference price for this heating fuel (e.g. community heating, oil, "
            "LPG), so heating and hot water can't be estimated. Ask the landlord for recent bills."
        )
    match = model.lookup(epc, prop.property_type.value, fuel)
    if match is None:
        return insufficient(
            f"Not enough Edinburgh EPC certificates in band {epc.value} to estimate heat demand."
        )
    dist = match.distribution
    is_gas = fuel is MainFuel.mains_gas
    rates = refs.energy_rates.gas if is_gas else refs.energy_rates.electricity
    standing_pence = rates.standing_charge_p_per_day * DAYS_PER_YEAR if is_gas else 0.0

    def monthly(kwh_per_m2: float) -> float:
        pence = area * kwh_per_m2 * rates.unit_rate_p_per_kwh + standing_pence
        return _annual_pence_to_monthly_gbp(pence)

    group = (
        f"band {epc.value}, {prop.property_type.value}, {fuel.value}"
        if match.level == "band_type_fuel"
        else f"band {epc.value} (all property types and fuels: no large enough detailed group)"
    )
    fuel_name = "gas" if is_gas else "electricity"
    note = (
        f"Estimate: {area:g} m² × {dist.median:g} kWh/m²/year (median calculated heat demand of "
        f"{dist.n:,} Edinburgh EPC certificates in {group}; interquartile range {dist.q1:g}-"
        f"{dist.q3:g} gives low/high) at {rates.unit_rate_p_per_kwh:g}p/kWh {fuel_name}"
    )
    note += (
        f" plus the gas standing charge ({rates.standing_charge_p_per_day:g}p/day)."
        if is_gas
        else " (the electricity standing charge is on the electricity line)."
    )
    note += (
        " Based on modelled heat demand, not fuel bought: heating system losses aren't "
        "included, so actual use is likely higher. " + _rates_period_note(refs)
    )
    return _line(
        CostKind.energy,
        label,
        value=monthly(dist.median),
        low=monthly(dist.q1),
        high=monthly(dist.q3),
        origin=Origin.estimate,
        source=f"{model_source}; {_rates_source(refs, fuel_name, rates)}",
        as_of=as_of,
        status=Status.estimated,
        note=note,
    )


def _electricity_line(prop: Property, refs: CostReferences, on: date) -> CostLine:
    label = "Estimated electricity (lighting, appliances, cooking)"
    if not refs.energy_rates.covers(on):
        return _rates_unavailable(refs, label, on)
    use = refs.electricity_use
    use_source = f"Ofgem typical domestic consumption values ({use.source_url})"
    as_of = min(use.meta.retrieved, refs.energy_rates.meta.retrieved)
    if not use.in_force(on):
        return _line(
            CostKind.energy,
            label,
            value=None,
            origin=Origin.estimate,
            source=use_source,
            as_of=as_of,
            status=Status.insufficient,
            note=f"The typical electricity use figures on file apply from "
            f"{use.valid_from.isoformat()}, not to {on.isoformat()}.",
        )
    rates = refs.energy_rates.electricity
    levels = use.electricity

    def monthly(kwh: int) -> float:
        pence = kwh * rates.unit_rate_p_per_kwh + rates.standing_charge_p_per_day * DAYS_PER_YEAR
        return _annual_pence_to_monthly_gbp(pence)

    note = (
        f"Estimate: Ofgem's typical household electricity use ({levels.medium_kwh_per_year:,} "
        f"kWh/year, median of GB single-rate households; low/high are the lower and upper "
        f"quartiles, {levels.low_kwh_per_year:,} and {levels.high_kwh_per_year:,} kWh, i.e. the "
        f"spread between households, not uncertainty about this property) at "
        f"{rates.unit_rate_p_per_kwh:g}p/kWh plus the standing charge "
        f"({rates.standing_charge_p_per_day:g}p/day). Not adjusted for this property's size or "
        "number of occupants."
    )
    if prop.main_fuel.value is MainFuel.electricity:
        note += (
            " This home has electric heating: the typical figure includes some households' "
            "electric heating, so adding it to the heating line may double-count part of it."
        )
    note += " " + _rates_period_note(refs)
    return _line(
        CostKind.energy,
        label,
        value=monthly(levels.medium_kwh_per_year),
        low=monthly(levels.low_kwh_per_year),
        high=monthly(levels.high_kwh_per_year),
        origin=Origin.estimate,
        source=f"{use_source}; {_rates_source(refs, 'electricity', rates)}",
        as_of=as_of,
        status=Status.estimated,
        note=note,
    )


# --- other recurring costs ------------------------------------------------------------


def _other_lines(prop: Property, profile: RenterProfile | None) -> list[CostLine]:
    costs = list(prop.other_recurring_costs)
    if profile is not None:
        costs += profile.other_recurring_costs
    return [CostLine(kind=CostKind.other, label=c.label, monthly_gbp=c.monthly_gbp) for c in costs]


# --- total + budget -------------------------------------------------------------------


def _total(
    lines: Sequence[CostLine], budget: float | None
) -> tuple[Evidence[float], float | None, float | None, BudgetComparison]:
    missing = [line.label for line in lines if line.monthly_gbp.value is None]
    if missing:
        total = Evidence[float](
            value=None,
            origin=Origin.estimate,
            source=ENGINE_SOURCE,
            status=Status.insufficient,
            note="The total can't be calculated while these lines are missing: "
            + "; ".join(missing)
            + ".",
        )
        return total, None, None, BudgetComparison.unknown

    values = [line.monthly_gbp.value for line in lines if line.monthly_gbp.value is not None]
    central = _gbp(sum(values))
    has_range = any(line.low_gbp is not None for line in lines)
    low = high = None
    if has_range:
        low = _gbp(sum(line.low_gbp if line.low_gbp is not None else v for line, v in _zip(lines)))
        high = _gbp(
            sum(line.high_gbp if line.high_gbp is not None else v for line, v in _zip(lines))
        )
    all_known = all(line.monthly_gbp.status is Status.known for line in lines)
    note = "Sum of the cost lines."
    if has_range:
        note += (
            " Low/high add up each line's low/high, so they show a rough spread, not a "
            "confidence interval."
        )

    comparison = BudgetComparison.unknown
    if budget is not None:
        comparison = BudgetComparison.within if central <= budget else BudgetComparison.over
        note += f" Compared with your budget of {_money(budget)} using the central estimate."
        if low is not None and high is not None and low <= budget < high:
            note += " The budget falls inside the low-high range, so it could go either way."

    total = Evidence[float](
        value=central,
        origin=Origin.estimate,
        source=ENGINE_SOURCE,
        status=Status.known if all_known else Status.estimated,
        note=note,
    )
    return total, low, high, comparison


def _zip(lines: Sequence[CostLine]) -> list[tuple[CostLine, float]]:
    return [(line, line.monthly_gbp.value) for line in lines if line.monthly_gbp.value is not None]


# --- entry point ----------------------------------------------------------------------


def estimate_monthly_cost(
    prop: Property,
    profile: RenterProfile | None,
    *,
    on: date | None = None,
    references: CostReferences | None = None,
) -> CostBreakdown:
    """Estimate the monthly cost of renting ``prop`` and compare it with ``profile``'s budget.

    ``on`` picks the council tax year and energy price cap period (default: today). Dates
    outside the reference data make the affected lines ``insufficient``; old figures are
    never reused silently. Without a profile (or a stated budget) the comparison is
    ``unknown``.
    """
    on = date.today() if on is None else on
    refs = load_cost_references() if references is None else references
    lines = [
        _rent_line(prop),
        _council_tax_line(prop, refs, on),
        _heating_line(prop, refs, on),
        _electricity_line(prop, refs, on),
        *_other_lines(prop, profile),
    ]
    budget = None if profile is None else profile.monthly_budget_gbp
    total, low, high, comparison = _total(lines, budget)
    return CostBreakdown(
        property_id=prop.id,
        profile_id=None if profile is None else profile.id,
        lines=lines,
        total_monthly_gbp=total,
        total_low_gbp=low,
        total_high_gbp=high,
        budget_monthly_gbp=budget,
        budget_comparison=comparison,
    )
