"""``POST /v1/properties/{id}/cost`` is served by the cost engine."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.engines import EngineBackend
from haven.api.fixtures import FixtureBackend
from haven.config import CONTRACT_EXAMPLES_DIR, Settings
from haven.cost import estimate_monthly_cost, load_cost_references
from haven.domain import CostBreakdown

Example = Callable[[str, str], Any]
ON = date(2026, 11, 7)  # inside the price cap period and council tax year on file
PAIRS = {
    "wheelchair_user": ("persona-wheelchair-user", "ill-prop-leith-flat"),
    "student": ("persona-student", "ill-prop-marchmont-flat"),
    "tight_budget": ("persona-tight-budget", "ill-prop-gorgie-flat"),
}


def make_client(on: date = ON) -> TestClient:
    return TestClient(create_app(backend=EngineBackend(CONTRACT_EXAMPLES_DIR, today=lambda: on)))


@pytest.fixture
def engine() -> TestClient:
    return make_client()


def post_cost(client: TestClient, property_id: str, profile_id: str | None = None) -> Any:
    body = {} if profile_id is None else {"profile_id": profile_id}
    return client.post(f"/v1/properties/{property_id}/cost", json=body)


def lines_by_label(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {line["label"]: line for line in body["lines"]}


def test_default_app_uses_the_engine() -> None:
    assert isinstance(create_app().state.backend, EngineBackend)


def test_fixtures_backend_still_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAVEN_BACKEND", "fixtures")
    backend = create_app().state.backend
    assert isinstance(backend, FixtureBackend) and not isinstance(backend, EngineBackend)
    assert Settings().backend == "fixtures"


@pytest.mark.parametrize("persona", list(PAIRS))
def test_persona_cost_matches_engine(engine: TestClient, example: Example, persona: str) -> None:
    profile_id, property_id = PAIRS[persona]
    response = post_cost(engine, property_id, profile_id)
    assert response.status_code == 200, response.text
    body = CostBreakdown.model_validate(response.json())

    prop = FixtureBackend(CONTRACT_EXAMPLES_DIR).get_property(property_id)
    profile = FixtureBackend(CONTRACT_EXAMPLES_DIR).get_profile(profile_id)
    expected = estimate_monthly_cost(prop, profile, on=ON, references=load_cost_references())
    assert body == expected
    # Engine figures, not the illustrative fixture numbers.
    assert response.json() != example(persona, "cost")
    assert body.property_id == property_id and body.profile_id == profile_id


def test_complete_inputs_give_estimated_total_and_budget_comparison(engine: TestClient) -> None:
    body = post_cost(engine, "ill-prop-leith-flat", "persona-wheelchair-user").json()
    kinds = [line["kind"] for line in body["lines"]]
    assert kinds == ["rent", "council_tax", "energy", "energy"]
    for line in body["lines"]:
        assert line["monthly_gbp"]["value"] is not None
        assert line["monthly_gbp"]["source"]
    energy = [line for line in body["lines"] if line["kind"] == "energy"]
    for line in energy:
        assert line["monthly_gbp"]["origin"] == "estimate"
        assert line["monthly_gbp"]["status"] == "estimated"
        assert line["low_gbp"] <= line["monthly_gbp"]["value"] <= line["high_gbp"]
    total = body["total_monthly_gbp"]
    assert total["status"] == "estimated"
    assert body["total_low_gbp"] <= total["value"] <= body["total_high_gbp"]
    assert body["budget_monthly_gbp"] == 1250.0
    expected = "within" if total["value"] <= 1250.0 else "over"
    assert body["budget_comparison"] == expected


def test_missing_band_makes_total_insufficient_not_zero(engine: TestClient) -> None:
    body = post_cost(engine, "ill-prop-marchmont-flat", "persona-student").json()
    council = next(line for line in body["lines"] if line["kind"] == "council_tax")
    assert council["monthly_gbp"]["value"] is None
    assert council["monthly_gbp"]["status"] == "insufficient"
    assert "band A" in council["monthly_gbp"]["note"]
    assert body["total_monthly_gbp"]["value"] is None
    assert body["total_monthly_gbp"]["status"] == "insufficient"
    assert body["budget_comparison"] == "unknown"
    assert body["budget_monthly_gbp"] == 900.0


def test_profile_recurring_costs_are_included(engine: TestClient) -> None:
    body = post_cost(engine, "ill-prop-gorgie-flat", "persona-tight-budget").json()
    other = [line for line in body["lines"] if line["kind"] == "other"]
    assert [line["label"] for line in other] == ["Broadband"]
    assert other[0]["monthly_gbp"]["origin"] == "user"


def test_without_profile_no_budget_comparison(engine: TestClient) -> None:
    response = post_cost(engine, "ill-prop-leith-flat")
    assert response.status_code == 200
    body = response.json()
    assert body["profile_id"] is None
    assert body["budget_monthly_gbp"] is None
    assert body["budget_comparison"] == "unknown"
    assert body["total_monthly_gbp"]["value"] is not None


def test_any_profile_property_pair_is_estimated(engine: TestClient) -> None:
    response = post_cost(engine, "ill-prop-leith-flat", "persona-student")
    assert response.status_code == 200
    body = response.json()
    assert body["profile_id"] == "persona-student"
    assert body["budget_monthly_gbp"] == 900.0


def test_created_property_is_estimated(engine: TestClient, example: Example) -> None:
    item = example("wheelchair_user", "properties")["items"][0]
    created = engine.post("/v1/properties", json={k: v for k, v in item.items() if k != "id"})
    assert created.status_code == 201
    new_id = created.json()["id"]
    body = post_cost(engine, new_id).json()
    reference = post_cost(engine, "ill-prop-leith-flat").json()
    assert body["property_id"] == new_id
    assert body["total_monthly_gbp"] == reference["total_monthly_gbp"]


def test_created_profile_is_used(engine: TestClient, example: Example) -> None:
    profile = {k: v for k, v in example("student", "profile").items() if k != "id"}
    profile["monthly_budget_gbp"] = 100.0
    created = engine.post("/v1/profiles", json=profile).json()
    body = post_cost(engine, "ill-prop-leith-flat", created["id"]).json()
    assert body["budget_comparison"] == "over"


def test_outside_reference_period_energy_is_insufficient() -> None:
    body = post_cost(make_client(date(2027, 2, 1)), "ill-prop-leith-flat").json()
    energy = [line for line in body["lines"] if line["kind"] == "energy"]
    assert energy and all(line["monthly_gbp"]["status"] == "insufficient" for line in energy)
    assert body["total_monthly_gbp"]["value"] is None


def test_unknown_property_is_404(engine: TestClient) -> None:
    response = post_cost(engine, "nope", "persona-student")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_unknown_profile_is_404(engine: TestClient) -> None:
    response = post_cost(engine, "ill-prop-leith-flat", "nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_other_endpoints_still_serve_fixtures(engine: TestClient, example: Example) -> None:
    profile_id, property_id = PAIRS["student"]
    # Profiles still come from the persona fixtures (suitability is now an engine: P2-08).
    response = engine.get(f"/v1/profiles/{profile_id}")
    assert response.json() == example("student", "profile")
    assert property_id
