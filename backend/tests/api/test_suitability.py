"""``POST /v1/properties/{id}/suitability`` served by the rules engine (P2-08)."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.engines import EngineBackend
from haven.config import CONTRACT_EXAMPLES_DIR
from haven.cost import estimate_monthly_cost
from haven.domain import Outcome, SuitabilityAssessment
from haven.location import CachedProvider
from haven.rules import evaluate_rules, location_for

ON = date(2026, 11, 7)


@pytest.fixture
def backend() -> EngineBackend:
    return EngineBackend(CONTRACT_EXAMPLES_DIR, today=lambda: ON)


@pytest.fixture
def client(backend: EngineBackend) -> TestClient:
    return TestClient(create_app(backend=backend))


def post(client: TestClient, property_id: str, profile_id: str) -> Any:
    return client.post(f"/v1/properties/{property_id}/suitability", json={"profile_id": profile_id})


@pytest.mark.parametrize(
    "profile_id", ["persona-student", "persona-tight-budget", "persona-wheelchair-user"]
)
def test_matches_direct_engine_run(
    client: TestClient, backend: EngineBackend, profile_id: str
) -> None:
    response = post(client, "seed-prop-leith", profile_id)
    assert response.status_code == 200
    prop = backend.get_property("seed-prop-leith")
    profile = backend.get_profile(profile_id)
    expected = SuitabilityAssessment(
        property_id=prop.id,
        profile_id=profile.id,
        findings=evaluate_rules(
            prop,
            profile,
            location_for(CachedProvider(), prop, profile),
            estimate_monthly_cost(prop, profile, on=ON),
        ),
    )
    assert response.json() == expected.model_dump(mode="json")


def test_wheelchair_user_at_leith_gets_access_concerns(client: TestClient) -> None:
    body = post(client, "seed-prop-leith", "persona-wheelchair-user").json()
    outcomes = {f["rule_id"]: f["outcome"] for f in body["findings"]}
    assert outcomes["step_free_entrance"] == Outcome.concern
    assert outcomes["lift_required_for_floor"] == Outcome.concern
    assert all(f["next_step"] for f in body["findings"] if f["outcome"] != Outcome.meets)


def test_property_without_location_data_is_unknown_not_fine(client: TestClient) -> None:
    # Persona fixture properties have no location cache: location rules must say unknown.
    body = post(client, "ill-prop-leith-flat", "persona-wheelchair-user").json()
    outcomes = {f["rule_id"]: f["outcome"] for f in body["findings"]}
    assert outcomes["walk_to_stop_within_limit"] == Outcome.unknown
    assert outcomes["travel_time_to_destinations"] == Outcome.unknown


def test_unknown_ids_are_404(client: TestClient) -> None:
    for property_id, profile_id in [("nope", "persona-student"), ("seed-prop-leith", "nope")]:
        response = post(client, property_id, profile_id)
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
