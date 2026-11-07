"""Each rule: meets / concern / unknown, plus registry behaviour."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from haven.cost import estimate_monthly_cost
from haven.domain import Finding, Outcome, Priority, Property, RenterProfile
from haven.location import (
    LocationContext,
    NearbyResult,
    Place,
    PlaceKind,
    Point,
    RouteProfile,
    RouteResult,
)
from haven.rules import REGISTRY, evaluate_rules, rule
from haven.rules.registry import always

ON = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)
ORIGIN = Point(latitude=55.95, longitude=-3.19)


def ev(value: Any, status: str = "known") -> dict[str, Any]:
    return {
        "value": value,
        "origin": "listing",
        "source": "test listing",
        "status": "insufficient" if value is None else status,
    }


def prop(**overrides: Any) -> Property:
    data: dict[str, Any] = {
        "id": "p",
        "title": "Test flat",
        "rent_pcm_gbp": ev(900.0),
        "bedrooms": ev(2),
        "property_type": ev("flat"),
        "floor_area_m2": ev(60.0),
        "council_tax_band": ev("C"),
        "epc_rating": ev("D"),
        "main_fuel": ev("mains_gas"),
        "floor_level": ev(0),
        "has_lift": ev(False),
        "entrance_steps": ev(0),
    }
    data.update(overrides)
    return Property.model_validate(data)


def profile(**overrides: Any) -> RenterProfile:
    data: dict[str, Any] = {"id": "r", "label": "Renter"}
    data.update(overrides)
    return RenterProfile.model_validate(data)


def place(kind: PlaceKind, distance: float, name: str | None = "Stop A") -> Place:
    return Place(
        kind=kind,
        name=name,
        latitude=55.95,
        longitude=-3.19,
        distance_m=distance,
        source="OpenStreetMap",
        fetched_at=NOW,
    )


def nearby(kind: PlaceKind, places: list[Place]) -> NearbyResult:
    return NearbyResult(
        kind=kind, radius_m=1500, status="known", places=places, source="OSM", fetched_at=NOW
    )


def stops_context(*places: Place, routes: list[RouteResult] | None = None) -> LocationContext:
    results = [
        nearby(kind, [p for p in places if p.kind is kind])
        for kind in (PlaceKind.bus_stop, PlaceKind.tram_stop, PlaceKind.rail_station)
    ]
    return LocationContext(property_id="p", origin=ORIGIN, nearby=results, routes=routes or [])


def route(
    name: str,
    *,
    profile_: RouteProfile = RouteProfile.foot_walking,
    distance: float = 1000,
    duration: float | None = 600,
    completeness: float | None = None,
) -> RouteResult:
    return RouteResult(
        profile=profile_,
        origin=ORIGIN,
        destination=Point(latitude=55.94, longitude=-3.2, name=name),
        status="known",
        distance_m=distance,
        duration_s=duration,
        data_completeness=completeness,
        source="openrouteservice",
        fetched_at=NOW,
    )


def run(
    rule_id: str,
    p: Property,
    r: RenterProfile,
    location: LocationContext | None = None,
    with_cost: bool = False,
) -> Finding:
    cost = estimate_monthly_cost(p, r, on=ON) if with_cost else None
    result = REGISTRY[rule_id].evaluate(p, r, location, cost)
    assert result.rule_id == rule_id
    assert (result.next_step is None) == (result.outcome is Outcome.meets)
    return result


# --- budget_fit -----------------------------------------------------------------------


def test_budget_fit() -> None:
    assert run("budget_fit", prop(), profile(monthly_budget_gbp=5000), with_cost=True).outcome == (
        Outcome.meets
    )
    over = run("budget_fit", prop(), profile(monthly_budget_gbp=500), with_cost=True)
    assert over.outcome is Outcome.concern and "over budget" in over.reason
    missing = run(
        "budget_fit",
        prop(council_tax_band=ev(None)),
        profile(monthly_budget_gbp=5000),
        with_cost=True,
    )
    assert missing.outcome is Outcome.unknown
    assert run("budget_fit", prop(), profile(monthly_budget_gbp=5000)).outcome is Outcome.unknown


# --- council_tax_band_known -------------------------------------------------------------


def test_council_tax_band_known() -> None:
    assert run("council_tax_band_known", prop(), profile()).outcome is Outcome.meets
    absent = run("council_tax_band_known", prop(council_tax_band=ev(None)), profile())
    assert absent.outcome is Outcome.concern
    inferred = prop(council_tax_band={**ev("B", "inferred"), "origin": "model"})
    assert run("council_tax_band_known", inferred, profile()).outcome is Outcome.unknown


# --- epc_heating_cost_risk --------------------------------------------------------------


def test_epc_heating_cost_risk() -> None:
    ok = run("epc_heating_cost_risk", prop(), profile(), with_cost=True)
    assert ok.outcome is Outcome.meets and "Estimated heating" in ok.reason
    bad = run("epc_heating_cost_risk", prop(epc_rating=ev("F")), profile(), with_cost=True)
    assert bad.outcome is Outcome.concern and "range £" in bad.reason
    assert run("epc_heating_cost_risk", prop(epc_rating=ev("G")), profile()).outcome is (
        Outcome.concern
    )
    assert run("epc_heating_cost_risk", prop(epc_rating=ev(None)), profile()).outcome is (
        Outcome.unknown
    )


# --- step_free_entrance -----------------------------------------------------------------


def test_step_free_entrance() -> None:
    needs = profile(access={"step_free_entrance_required": True})
    assert run("step_free_entrance", prop(), needs).outcome is Outcome.meets
    steps = run("step_free_entrance", prop(entrance_steps=ev(4)), needs)
    assert steps.outcome is Outcome.concern and "4 step" in steps.reason
    assert run("step_free_entrance", prop(entrance_steps=ev(None)), needs).outcome is (
        Outcome.unknown
    )
    assert run("step_free_entrance", prop(entrance_steps=ev(0, "uncertain")), needs).outcome is (
        Outcome.unknown
    )


def test_step_free_applies_to() -> None:
    applies = REGISTRY["step_free_entrance"].applies_to
    assert not applies(profile())
    assert applies(profile(access={"wheelchair_user": True}))
    assert applies(profile(priorities=[Priority.step_free_access]))


# --- lift_required_for_floor ------------------------------------------------------------


def test_lift_required_for_floor() -> None:
    needs = profile(access={"lift_required_above_floor": 1})
    assert run("lift_required_for_floor", prop(floor_level=ev(1)), needs).outcome is Outcome.meets
    assert run("lift_required_for_floor", prop(floor_level=ev(3)), needs).outcome is (
        Outcome.concern
    )
    lift = prop(floor_level=ev(3), has_lift=ev(True))
    assert run("lift_required_for_floor", lift, needs).outcome is Outcome.meets
    no_info = prop(floor_level=ev(3), has_lift=ev(None))
    assert run("lift_required_for_floor", no_info, needs).outcome is Outcome.unknown
    assert run("lift_required_for_floor", prop(floor_level=ev(None)), needs).outcome is (
        Outcome.unknown
    )


def test_lift_applies_to() -> None:
    applies = REGISTRY["lift_required_for_floor"].applies_to
    assert not applies(profile())
    wheelchair = profile(access={"wheelchair_user": True})
    assert applies(wheelchair)
    assert run("lift_required_for_floor", prop(floor_level=ev(1)), wheelchair).outcome is (
        Outcome.concern
    )
    assert applies(profile(priorities=[Priority.lift_access]))


# --- walk_to_stop_within_limit ----------------------------------------------------------


WALKER = profile(access={"max_walk_to_stop_m": 400})


def test_walk_to_stop_estimated() -> None:
    near = stops_context(place(PlaceKind.bus_stop, 200), place(PlaceKind.tram_stop, 900))
    result = run("walk_to_stop_within_limit", prop(), WALKER, near)
    assert result.outcome is Outcome.meets and "estimated" in result.reason
    far = stops_context(place(PlaceKind.bus_stop, 600))
    assert run("walk_to_stop_within_limit", prop(), WALKER, far).outcome is Outcome.concern
    borderline = stops_context(place(PlaceKind.bus_stop, 350))
    assert run("walk_to_stop_within_limit", prop(), WALKER, borderline).outcome is Outcome.unknown


def test_walk_to_stop_uses_route_when_cached() -> None:
    stop = place(PlaceKind.bus_stop, 350, name="Stop A")
    ok = stops_context(stop, routes=[route("Stop A", distance=390)])
    assert run("walk_to_stop_within_limit", prop(), WALKER, ok).outcome is Outcome.meets
    long = stops_context(stop, routes=[route("Stop A", distance=520)])
    assert run("walk_to_stop_within_limit", prop(), WALKER, long).outcome is Outcome.concern


def test_walk_to_stop_without_data() -> None:
    assert run("walk_to_stop_within_limit", prop(), WALKER, None).outcome is Outcome.unknown
    partial = LocationContext(
        property_id="p", origin=ORIGIN, nearby=[nearby(PlaceKind.bus_stop, [])]
    )
    assert run("walk_to_stop_within_limit", prop(), WALKER, partial).outcome is Outcome.unknown
    none_found = run("walk_to_stop_within_limit", prop(), WALKER, stops_context())
    assert (
        none_found.outcome is Outcome.concern and "No bus, tram or rail stop" in none_found.reason
    )


# --- travel_time_to_destinations --------------------------------------------------------

COMMUTER = profile(
    destinations=[
        {"name": "Uni", "latitude": 55.94, "longitude": -3.19, "max_travel_minutes": 20},
        {"name": "Gym", "latitude": 55.94, "longitude": -3.18},
    ]
)


def test_travel_time() -> None:
    def ctx(*routes: RouteResult) -> LocationContext:
        return LocationContext(property_id="p", origin=ORIGIN, routes=list(routes))

    assert run("travel_time_to_destinations", prop(), COMMUTER, ctx(route("Uni"))).outcome is (
        Outcome.meets
    )
    slow = ctx(route("Uni", duration=1800))
    assert run("travel_time_to_destinations", prop(), COMMUTER, slow).outcome is Outcome.concern
    assert run("travel_time_to_destinations", prop(), COMMUTER, ctx()).outcome is Outcome.unknown
    assert run("travel_time_to_destinations", prop(), COMMUTER, None).outcome is Outcome.unknown
    assert not REGISTRY["travel_time_to_destinations"].applies_to(profile())


# --- wheelchair_route_data_completeness -------------------------------------------------

WHEELCHAIR = profile(access={"wheelchair_user": True})


def test_wheelchair_route_data_completeness() -> None:
    def ctx(*completeness: float | None) -> LocationContext:
        routes = [
            route(f"D{i}", profile_=RouteProfile.wheelchair, completeness=c)
            for i, c in enumerate(completeness)
        ]
        return LocationContext(property_id="p", origin=ORIGIN, routes=routes)

    rid = "wheelchair_route_data_completeness"
    assert run(rid, prop(), WHEELCHAIR, ctx(0.8, 0.6)).outcome is Outcome.meets
    low = run(rid, prop(), WHEELCHAIR, ctx(0.8, 0.2))
    assert low.outcome is Outcome.concern and "20%" in low.reason
    assert run(rid, prop(), WHEELCHAIR, ctx(None)).outcome is Outcome.unknown
    assert run(rid, prop(), WHEELCHAIR, None).outcome is Outcome.unknown


# --- registry ---------------------------------------------------------------------------


def test_evaluate_rules_runs_only_applicable_rules() -> None:
    p = prop()
    basic = evaluate_rules(p, profile(), None, estimate_monthly_cost(p, None, on=ON))
    assert [f.rule_id for f in basic] == ["council_tax_band_known", "epc_heating_cost_risk"]
    everyone = profile(
        monthly_budget_gbp=1500,
        access={"wheelchair_user": True, "max_walk_to_stop_m": 400},
        destinations=COMMUTER.destinations,
    )
    ids = {f.rule_id for f in evaluate_rules(p, everyone, None, None)}
    assert ids == set(REGISTRY)
    assert len(REGISTRY) == 8


def test_duplicate_rule_rejected() -> None:
    with pytest.raises(ValueError, match="already registered"):
        rule("budget_fit", category=REGISTRY["budget_fit"].category, title="x")(
            REGISTRY["budget_fit"].evaluate
        )
    assert always(profile())


def test_no_overall_score_field() -> None:
    assert not {"score", "rating", "grade"} & set(Finding.model_fields)
