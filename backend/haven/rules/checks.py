"""The v1 rules. Importing this module registers them (see :mod:`haven.rules.registry`).

Wording follows the project constraints: facts are attributed ("the listing reports ..."),
access and condition are never stated as certain, and anything the data can't settle is
``unknown`` with a next step, never quietly "fine".
"""

from haven.domain import (
    BudgetComparison,
    CostBreakdown,
    CostKind,
    CostLine,
    EpcBand,
    Finding,
    FindingCategory,
    Outcome,
    Priority,
    Property,
    RenterProfile,
    Status,
)
from haven.location import LocationContext, PlaceKind, RouteProfile, RouteResult
from haven.rules.registry import fact, finding, rule, user_fact

# Walking distance is at least the straight-line distance; without a routed path Haven
# approximates it as straight-line x 1.3 (the same factor build_routes.py uses as fallback).
DETOUR_FACTOR = 1.3
# Haven's own threshold (not an external standard): below this share of route segments with
# kerb/incline/surface tags, the wheelchair route's accessibility is treated as unverified.
MIN_ROUTE_COMPLETENESS = 0.5
HIGH_HEATING_RISK_BANDS = {EpcBand.E, EpcBand.F, EpcBand.G}
STOP_KINDS = (PlaceKind.bus_stop, PlaceKind.tram_stop, PlaceKind.rail_station)


def _money(value: float) -> str:
    return f"£{value:,.0f}"


def _route_profile(profile: RenterProfile) -> RouteProfile:
    return RouteProfile.wheelchair if profile.access.wheelchair_user else RouteProfile.foot_walking


# --- cost -------------------------------------------------------------------------------


@rule(
    "budget_fit",
    category=FindingCategory.cost,
    title="Estimated monthly cost against your budget",
    applies_to=lambda p: p.monthly_budget_gbp is not None,
)
def budget_fit(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    budget = profile.monthly_budget_gbp
    facts = [user_fact("monthly_budget_gbp", budget)]
    if cost is None or cost.budget_comparison is BudgetComparison.unknown:
        missing = "" if cost is None else f" ({cost.total_monthly_gbp.note})"
        return finding(
            "budget_fit",
            prop,
            profile,
            Outcome.unknown,
            f"The total monthly cost can't be estimated yet{missing}",
            facts=facts,
            next_step="Ask the landlord for the missing details (e.g. council tax band, EPC).",
        )
    total = cost.total_monthly_gbp
    facts.append(fact("total_monthly_gbp", total))
    spread = ""
    if cost.total_low_gbp is not None and cost.total_high_gbp is not None:
        spread = f" (rough range {_money(cost.total_low_gbp)}-{_money(cost.total_high_gbp)})"
    assert total.value is not None and budget is not None
    summary = (
        f"Estimated total {_money(total.value)} a month{spread} against your budget of "
        f"{_money(budget)}."
    )
    if cost.budget_comparison is BudgetComparison.within:
        return finding("budget_fit", prop, profile, Outcome.meets, summary, facts=facts)
    return finding(
        "budget_fit",
        prop,
        profile,
        Outcome.concern,
        summary + " The estimate is over budget.",
        facts=facts,
        next_step="Check the cost lines: ask for recent energy bills and any service charges.",
    )


@rule(
    "council_tax_band_known",
    category=FindingCategory.missing_info,
    title="Council tax band",
)
def council_tax_band_known(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    band = prop.council_tax_band
    facts = [fact("council_tax_band", band)]
    if band.value is None:
        return finding(
            "council_tax_band_known",
            prop,
            profile,
            Outcome.concern,
            "The listing doesn't state the council tax band, so the monthly cost is incomplete.",
            facts=facts,
            next_step="Ask the landlord for the band, or look it up on the Scottish Assessors "
            "Association website.",
        )
    if band.status is not Status.known:
        return finding(
            "council_tax_band_known",
            prop,
            profile,
            Outcome.unknown,
            f"Council tax band {band.value.value} is {band.status.value}, not confirmed.",
            facts=facts,
            next_step="Confirm the band with the landlord or the Scottish Assessors Association.",
        )
    return finding(
        "council_tax_band_known",
        prop,
        profile,
        Outcome.meets,
        f"The listing states council tax band {band.value.value}.",
        facts=facts,
    )


def _heating_line(cost: CostBreakdown | None) -> CostLine | None:
    if cost is None:
        return None
    return next(
        (
            line
            for line in cost.lines
            if line.kind is CostKind.energy and line.label.startswith("Estimated heating")
        ),
        None,
    )


@rule(
    "epc_heating_cost_risk",
    category=FindingCategory.cost,
    title="Heating cost risk from the EPC rating",
)
def epc_heating_cost_risk(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    epc = prop.epc_rating
    facts = [fact("epc_rating", epc)]
    if epc.value is None:
        return finding(
            "epc_heating_cost_risk",
            prop,
            profile,
            Outcome.unknown,
            "The listing doesn't give an EPC rating, so heating cost risk can't be judged.",
            facts=facts,
            next_step="Ask for the EPC certificate (landlords must provide one).",
        )
    heating = _heating_line(cost)
    estimate = ""
    if heating is not None and heating.monthly_gbp.value is not None:
        facts.append(fact("estimated_heating_monthly_gbp", heating.monthly_gbp))
        estimate = f" Estimated heating and hot water: {_money(heating.monthly_gbp.value)} a month"
        if heating.low_gbp is not None and heating.high_gbp is not None:
            estimate += f" (range {_money(heating.low_gbp)}-{_money(heating.high_gbp)})"
        estimate += "."
    if epc.value in HIGH_HEATING_RISK_BANDS:
        return finding(
            "epc_heating_cost_risk",
            prop,
            profile,
            Outcome.concern,
            f"EPC band {epc.value.value}: homes in bands E-G tend to cost more to heat." + estimate,
            facts=facts,
            next_step="Ask for recent energy bills and what heating system and insulation the "
            "home has.",
        )
    return finding(
        "epc_heating_cost_risk",
        prop,
        profile,
        Outcome.meets,
        f"EPC band {epc.value.value} (not in the higher-cost bands E-G)." + estimate,
        facts=facts,
    )


# --- access -----------------------------------------------------------------------------


def _needs_step_free(profile: RenterProfile) -> bool:
    access = profile.access
    return (
        access.wheelchair_user
        or access.step_free_entrance_required
        or Priority.step_free_access in profile.priorities
    )


@rule(
    "step_free_entrance",
    category=FindingCategory.access,
    title="Step-free entrance",
    applies_to=_needs_step_free,
)
def step_free_entrance(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    steps = prop.entrance_steps
    facts = [fact("entrance_steps", steps)]
    if steps.value is None:
        return finding(
            "step_free_entrance",
            prop,
            profile,
            Outcome.unknown,
            "The listing doesn't say whether the entrance has steps.",
            facts=facts,
            next_step="Ask the landlord for photos of the entrance, or check it at a viewing.",
        )
    if steps.value > 0:
        return finding(
            "step_free_entrance",
            prop,
            profile,
            Outcome.concern,
            f"The listing reports {steps.value} step(s) at the entrance.",
            facts=facts,
            next_step="Ask whether there is a step-free alternative entrance or a ramp.",
        )
    if steps.status is not Status.known:
        return finding(
            "step_free_entrance",
            prop,
            profile,
            Outcome.unknown,
            f"No entrance steps, but this is {steps.status.value}, not confirmed.",
            facts=facts,
            next_step="Confirm the entrance is step-free at a viewing.",
        )
    return finding(
        "step_free_entrance",
        prop,
        profile,
        Outcome.meets,
        "The listing reports no steps at the entrance; confirm at a viewing.",
        facts=facts,
    )


def _lift_threshold(profile: RenterProfile) -> int | None:
    """Highest floor reachable without a lift, or ``None`` if the renter needs no lift."""
    access = profile.access
    if access.lift_required_above_floor is not None:
        return access.lift_required_above_floor
    if access.wheelchair_user or Priority.lift_access in profile.priorities:
        return 0
    return None


@rule(
    "lift_required_for_floor",
    category=FindingCategory.access,
    title="Lift for the property's floor",
    applies_to=lambda p: _lift_threshold(p) is not None,
)
def lift_required_for_floor(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    threshold = _lift_threshold(profile)
    assert threshold is not None
    floor, lift = prop.floor_level, prop.has_lift
    facts = [fact("floor_level", floor), user_fact("lift_required_above_floor", threshold)]
    if floor.value is None:
        return finding(
            "lift_required_for_floor",
            prop,
            profile,
            Outcome.unknown,
            "The listing doesn't say which floor the property is on.",
            facts=facts,
            next_step="Ask the landlord which floor it is on and whether there is a lift.",
        )
    if floor.value <= threshold:
        return finding(
            "lift_required_for_floor",
            prop,
            profile,
            Outcome.meets,
            f"Floor {floor.value}: within the floors you can reach without a lift.",
            facts=facts,
        )
    facts.append(fact("has_lift", lift))
    if lift.value is None:
        return finding(
            "lift_required_for_floor",
            prop,
            profile,
            Outcome.unknown,
            f"Floor {floor.value} needs a lift for you, and the listing doesn't say if there "
            "is one.",
            facts=facts,
            next_step="Ask whether there is a lift and how reliable it is.",
        )
    if not lift.value:
        return finding(
            "lift_required_for_floor",
            prop,
            profile,
            Outcome.concern,
            f"Floor {floor.value} needs a lift for you, and the listing reports no lift.",
            facts=facts,
            next_step="Look for a ground-floor or lift-served property, or confirm access.",
        )
    return finding(
        "lift_required_for_floor",
        prop,
        profile,
        Outcome.meets,
        f"Floor {floor.value}; the listing reports a lift (its reliability isn't known).",
        facts=facts,
    )


# --- location ---------------------------------------------------------------------------


@rule(
    "walk_to_stop_within_limit",
    category=FindingCategory.location,
    title="Walk to the nearest public transport stop",
    applies_to=lambda p: p.access.max_walk_to_stop_m is not None,
)
def walk_to_stop_within_limit(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    limit = profile.access.max_walk_to_stop_m
    assert limit is not None
    facts = [user_fact("max_walk_to_stop_m", limit)]
    unknown_step = "Check the walk to the nearest stop on a map or at a viewing."
    results = [location.nearby_for(k) for k in STOP_KINDS] if location is not None else []
    searched = [r for r in results if r is not None and r.status is Status.known]
    if not searched or len(searched) < len(STOP_KINDS):
        return finding(
            "walk_to_stop_within_limit",
            prop,
            profile,
            Outcome.unknown,
            "There is no transport stop data for this property yet.",
            facts=facts,
            next_step=unknown_step,
        )
    stops = [p for r in searched for p in r.places]
    nearest = min(stops, key=lambda p: p.distance_m, default=None)
    if nearest is None:
        radius = min(r.radius_m for r in searched)
        return finding(
            "walk_to_stop_within_limit",
            prop,
            profile,
            Outcome.concern,
            f"No bus, tram or rail stop was found within {radius:,.0f} m (OpenStreetMap).",
            facts=facts,
            next_step=unknown_step,
        )
    label = f"{nearest.kind.value.replace('_', ' ')} {nearest.name or '(unnamed)'}"
    straight = nearest.distance_m
    if location is not None and nearest.name:
        route = location.route_to(nearest.name, _route_profile(profile))
        if route is not None and route.distance_m is not None:
            ok = route.distance_m <= limit
            return finding(
                "walk_to_stop_within_limit",
                prop,
                profile,
                Outcome.meets if ok else Outcome.concern,
                f"Nearest stop: {label}, {route.distance_m:,.0f} m by {route.status.value} route "
                f"({route.source}); your limit is {limit:,} m.",
                facts=facts,
                next_step=None if ok else unknown_step,
            )
    if straight > limit:
        return finding(
            "walk_to_stop_within_limit",
            prop,
            profile,
            Outcome.concern,
            f"Nearest stop: {label}, {straight:,.0f} m in a straight line, already over your "
            f"{limit:,} m limit.",
            facts=facts,
            next_step=unknown_step,
        )
    estimate = straight * DETOUR_FACTOR
    if estimate <= limit:
        return finding(
            "walk_to_stop_within_limit",
            prop,
            profile,
            Outcome.meets,
            f"Nearest stop: {label}, about {estimate:,.0f} m walking (estimated: straight line "
            f"x {DETOUR_FACTOR}, no route checked); your limit is {limit:,} m.",
            facts=facts,
        )
    return finding(
        "walk_to_stop_within_limit",
        prop,
        profile,
        Outcome.unknown,
        f"Nearest stop: {label}, {straight:,.0f} m in a straight line; the walking distance "
        f"may be over your {limit:,} m limit.",
        facts=facts,
        next_step=unknown_step,
    )


@rule(
    "travel_time_to_destinations",
    category=FindingCategory.location,
    title="Travel time to your destinations",
    applies_to=lambda p: any(d.max_travel_minutes is not None for d in p.destinations),
)
def travel_time_to_destinations(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    mode = _route_profile(profile)
    parts: list[str] = []
    outcomes: list[Outcome] = []
    for dest in profile.destinations:
        if dest.max_travel_minutes is None:
            continue
        route = location.route_to(dest.name, mode) if location is not None else None
        if route is None or route.duration_s is None:
            outcomes.append(Outcome.unknown)
            parts.append(f"{dest.name}: no route yet")
            continue
        minutes = route.duration_s / 60
        ok = minutes <= dest.max_travel_minutes
        outcomes.append(Outcome.meets if ok else Outcome.concern)
        parts.append(
            f"{dest.name}: {minutes:.0f} min ({route.status.value}) vs {dest.max_travel_minutes} "
            "min limit"
        )
    reason = (
        f"{mode.value.replace('_', ' ')} times (public transport isn't modelled): "
        + "; ".join(parts)
        + "."
    )
    if Outcome.concern in outcomes:
        outcome = Outcome.concern
    elif Outcome.unknown in outcomes:
        outcome = Outcome.unknown
    else:
        outcome = Outcome.meets
    return finding(
        "travel_time_to_destinations",
        prop,
        profile,
        outcome,
        reason,
        next_step=None
        if outcome is Outcome.meets
        else "Check journey times with a journey planner (e.g. Lothian Buses or Traveline).",
    )


@rule(
    "wheelchair_route_data_completeness",
    category=FindingCategory.access,
    title="Accessibility data on wheelchair routes",
    applies_to=lambda p: p.access.wheelchair_user,
)
def wheelchair_route_data_completeness(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> Finding:
    routes: list[RouteResult] = []
    if location is not None:
        routes = [
            r
            for r in location.routes
            if r.profile is RouteProfile.wheelchair and r.data_completeness is not None
        ]
    if not routes:
        return finding(
            "wheelchair_route_data_completeness",
            prop,
            profile,
            Outcome.unknown,
            "No wheelchair routes with accessibility data are available for this property yet.",
            next_step="Check kerbs, slopes and surfaces on your usual routes in person.",
        )
    worst = min(routes, key=lambda r: r.data_completeness or 0.0)
    share = worst.data_completeness or 0.0
    name = worst.destination.name or "a destination"
    if share < MIN_ROUTE_COMPLETENESS:
        return finding(
            "wheelchair_route_data_completeness",
            prop,
            profile,
            Outcome.concern,
            f"The route to {name} has kerb/slope/surface data for only {share:.0%} of its "
            "length, so its accessibility is largely unverified.",
            next_step="Check kerbs, slopes and surfaces on this route in person.",
        )
    return finding(
        "wheelchair_route_data_completeness",
        prop,
        profile,
        Outcome.meets,
        f"Every wheelchair route has accessibility data for at least {share:.0%} of its length "
        "(data coverage, not a guarantee the route is accessible).",
    )
