"""The stub API serves the contract examples through the FixtureBackend."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.fixtures import PERSONAS
from haven.config import Settings

Example = Callable[[str, str], Any]

PAIRS = {
    "wheelchair_user": ("persona-wheelchair-user", "ill-prop-leith-flat"),
    "student": ("persona-student", "ill-prop-marchmont-flat"),
    "tight_budget": ("persona-tight-budget", "ill-prop-gorgie-flat"),
}
PROBLEM = "application/problem+json"


def assert_problem(response: Any, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith(PROBLEM)
    body: dict[str, Any] = response.json()
    assert body["status"] == status
    assert body["title"]
    assert body["instance"] == response.request.url.path
    return body


# --- profiles --------------------------------------------------------------------------


def test_list_profiles_returns_all_personas(client: TestClient, example: Example) -> None:
    response = client.get("/v1/profiles")
    assert response.status_code == 200
    assert response.json() == {"items": [example(p, "profile") for p in PERSONAS]}


@pytest.mark.parametrize("persona", PERSONAS)
def test_get_profile(client: TestClient, example: Example, persona: str) -> None:
    profile_id, _ = PAIRS[persona]
    response = client.get(f"/v1/profiles/{profile_id}")
    assert response.status_code == 200
    assert response.json() == example(persona, "profile")


def test_create_profile_assigns_id_and_can_be_fetched(client: TestClient, example: Example) -> None:
    body = {k: v for k, v in example("student", "profile").items() if k != "id"}
    response = client.post("/v1/profiles", json=body)
    assert response.status_code == 201
    created = response.json()
    assert created["id"] and created["id"] != "persona-student"
    assert {k: v for k, v in created.items() if k != "id"} == body
    assert client.get(f"/v1/profiles/{created['id']}").json() == created
    assert created in client.get("/v1/profiles").json()["items"]


def test_create_profile_validation_error_is_problem_json(client: TestClient) -> None:
    response = client.post("/v1/profiles", json={"label": "x", "monthly_budget_gbp": -5})
    body = assert_problem(response, 422)
    assert body["errors"]
    assert body["errors"][0]["loc"] == ["body", "monthly_budget_gbp"]
    assert body["errors"][0]["type"] == "greater_than"


def test_create_profile_rejects_client_id(client: TestClient) -> None:
    assert_problem(client.post("/v1/profiles", json={"id": "mine", "label": "x"}), 422)


def test_unknown_profile_is_404(client: TestClient) -> None:
    body = assert_problem(client.get("/v1/profiles/nope"), 404)
    assert "nope" in body["detail"]
    assert body["errors"] is None


# --- properties ------------------------------------------------------------------------


def test_list_properties_unions_persona_properties(
    fixture_client: TestClient, example: Example
) -> None:
    response = fixture_client.get("/v1/properties")
    assert response.status_code == 200
    expected = [item for p in PERSONAS for item in example(p, "properties")["items"]]
    assert response.json() == {"items": expected}


def test_engine_list_properties_adds_persona_properties_after_seed(
    client: TestClient, example: Example
) -> None:
    # The engine backend lists the seed first (tests/seed covers that), then the personas.
    items = client.get("/v1/properties").json()["items"]
    expected = [item for p in PERSONAS for item in example(p, "properties")["items"]]
    assert items[-len(expected) :] == expected


@pytest.mark.parametrize("persona", PERSONAS)
def test_get_property(client: TestClient, example: Example, persona: str) -> None:
    _, property_id = PAIRS[persona]
    response = client.get(f"/v1/properties/{property_id}")
    assert response.status_code == 200
    assert response.json() == example(persona, "properties")["items"][0]


def test_unknown_property_is_404(client: TestClient) -> None:
    assert_problem(client.get("/v1/properties/ill-prop-does-not-exist"), 404)


def test_create_property(client: TestClient, example: Example) -> None:
    body = {k: v for k, v in example("student", "properties")["items"][0].items() if k != "id"}
    response = client.post("/v1/properties", json=body)
    assert response.status_code == 201
    created = response.json()
    assert {k: v for k, v in created.items() if k != "id"} == body
    assert client.get(f"/v1/properties/{created['id']}").json() == created


def test_create_property_rejects_value_without_insufficient_status(
    client: TestClient, example: Example
) -> None:
    body = {k: v for k, v in example("student", "properties")["items"][0].items() if k != "id"}
    body["has_lift"] = {**body["has_lift"], "value": None, "status": "known"}
    assert_problem(client.post("/v1/properties", json=body), 422)


# --- cost + suitability ----------------------------------------------------------------


# Cost is served by the cost engine by default (tests/api/test_cost.py); these cover the
# fixtures-only backend (HAVEN_BACKEND=fixtures).


@pytest.mark.parametrize("persona", PERSONAS)
def test_cost_for_persona(fixture_client: TestClient, example: Example, persona: str) -> None:
    profile_id, property_id = PAIRS[persona]
    response = fixture_client.post(
        f"/v1/properties/{property_id}/cost", json={"profile_id": profile_id}
    )
    assert response.status_code == 200
    assert response.json() == example(persona, "cost")


def test_cost_without_profile_has_no_budget_comparison(fixture_client: TestClient) -> None:
    response = fixture_client.post("/v1/properties/ill-prop-leith-flat/cost", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["profile_id"] is None
    assert body["budget_monthly_gbp"] is None
    assert body["budget_comparison"] == "unknown"


def test_cost_for_unmatched_pair_is_not_invented(fixture_client: TestClient) -> None:
    response = fixture_client.post(
        "/v1/properties/ill-prop-leith-flat/cost", json={"profile_id": "persona-student"}
    )
    body = assert_problem(response, 501)
    assert "fixture" in body["detail"]


def test_cost_for_created_property_is_not_invented(
    fixture_client: TestClient, example: Example
) -> None:
    body = {k: v for k, v in example("student", "properties")["items"][0].items() if k != "id"}
    created = fixture_client.post("/v1/properties", json=body).json()
    assert_problem(fixture_client.post(f"/v1/properties/{created['id']}/cost", json={}), 501)


def test_cost_unknown_profile_is_404(fixture_client: TestClient) -> None:
    response = fixture_client.post(
        "/v1/properties/ill-prop-leith-flat/cost", json={"profile_id": "x"}
    )
    assert_problem(response, 404)


@pytest.mark.parametrize("persona", PERSONAS)
def test_suitability_for_persona(
    fixture_client: TestClient, example: Example, persona: str
) -> None:
    profile_id, property_id = PAIRS[persona]
    response = fixture_client.post(
        f"/v1/properties/{property_id}/suitability", json={"profile_id": profile_id}
    )
    assert response.status_code == 200
    assert response.json() == example(persona, "suitability")


def test_suitability_requires_profile(client: TestClient) -> None:
    body = assert_problem(
        client.post("/v1/properties/ill-prop-leith-flat/suitability", json={}), 422
    )
    assert body["errors"][0]["loc"] == ["body", "profile_id"]


def test_suitability_unknown_property_is_404(client: TestClient) -> None:
    response = client.post(
        "/v1/properties/nope/suitability", json={"profile_id": "persona-student"}
    )
    assert_problem(response, 404)


# --- uploads ---------------------------------------------------------------------------


def test_upload_records_file_without_claiming_screening(fixture_client: TestClient) -> None:
    response = fixture_client.post(
        "/v1/uploads",
        files={"file": ("sub/dir/kitchen.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg")},
        data={"kind": "photo", "property_id": "ill-prop-leith-flat"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "kitchen.jpg"
    assert body["content_type"] == "image/jpeg"
    assert body["size_bytes"] == len(b"\xff\xd8\xff fake jpeg")
    assert body["property_id"] == "ill-prop-leith-flat"
    assert body["signals"] == []
    assert body["evidence_quality"] is None
    assert body["metadata_stripped"] is False


def test_upload_requires_kind_and_file(fixture_client: TestClient) -> None:
    assert_problem(fixture_client.post("/v1/uploads", data={"kind": "photo"}), 422)
    files = {"file": ("a.jpg", b"x", "image/jpeg")}
    assert_problem(fixture_client.post("/v1/uploads", files=files, data={"kind": "selfie"}), 422)


def test_upload_unknown_property_is_404(fixture_client: TestClient) -> None:
    response = fixture_client.post(
        "/v1/uploads",
        files={"file": ("a.jpg", b"x", "image/jpeg")},
        data={"kind": "photo", "property_id": "nope"},
    )
    assert_problem(response, 404)


def test_delete_upload(fixture_client: TestClient) -> None:
    created = fixture_client.post(
        "/v1/uploads",
        files={"file": ("a.pdf", b"%PDF-1.7", "application/pdf")},
        data={"kind": "document"},
    ).json()
    response = fixture_client.delete(f"/v1/uploads/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert_problem(fixture_client.delete(f"/v1/uploads/{created['id']}"), 404)


def test_delete_fixture_upload(fixture_client: TestClient) -> None:
    assert fixture_client.delete("/v1/uploads/ill-upload-wu-entrance").status_code == 204


# --- assessments + reports -------------------------------------------------------------


@pytest.mark.parametrize("persona", PERSONAS)
def test_assessment_returns_persona_report(
    client: TestClient, example: Example, persona: str
) -> None:
    profile_id, property_id = PAIRS[persona]
    report = example(persona, "report")
    response = client.post(
        "/v1/assessments", json={"profile_id": profile_id, "property_id": property_id}
    )
    assert response.status_code == 201
    assert response.json() == report
    assert client.get(f"/v1/reports/{report['id']}").json() == report


def test_assessment_unknown_upload_is_404(client: TestClient) -> None:
    body = {
        "profile_id": "persona-student",
        "property_id": "ill-prop-marchmont-flat",
        "upload_ids": ["nope"],
    }
    assert_problem(client.post("/v1/assessments", json=body), 404)


def test_assessment_unmatched_pair_is_501(client: TestClient) -> None:
    body = {"profile_id": "persona-student", "property_id": "ill-prop-gorgie-flat"}
    assert_problem(client.post("/v1/assessments", json=body), 501)


def test_unknown_report_is_404(client: TestClient) -> None:
    assert_problem(client.get("/v1/reports/nope"), 404)


def test_reports_always_carry_disclaimer(client: TestClient) -> None:
    body = client.get("/v1/reports/ill-report-wu").json()
    assert "not a legal, safety, accessibility or compliance certification" in body["disclaimer"]


# --- meta, errors, CORS ----------------------------------------------------------------


def test_meta_enums_cover_every_value_with_labels(client: TestClient) -> None:
    response = client.get("/v1/meta/enums")
    assert response.status_code == 200
    enums = response.json()["enums"]
    assert [o["value"] for o in enums["likelihood"]] == [
        "unlikely",
        "possible",
        "likely",
        "insufficient_evidence",
    ]
    labels = {o["value"]: o["label"] for o in enums["likelihood"]}
    assert labels["insufficient_evidence"] == "Insufficient evidence"
    outcome = {o["value"]: o["label"] for o in enums["outcome"]}
    assert outcome["unknown"] != outcome["concern"]
    for options in enums.values():
        assert options and all(o["label"] for o in options)


def test_unknown_route_is_problem_json(client: TestClient) -> None:
    assert_problem(client.get("/v1/does-not-exist"), 404)


def test_cors_origins_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAVEN_CORS_ORIGINS", "http://localhost:5173, https://ui.example")
    client = TestClient(create_app())
    headers = {"Origin": "https://ui.example", "Access-Control-Request-Method": "GET"}
    response = client.options("/v1/properties", headers=headers)
    assert response.headers["access-control-allow-origin"] == "https://ui.example"
    other = client.get("/v1/properties", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_no_cors_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HAVEN_CORS_ORIGINS", raising=False)
    response = TestClient(create_app()).get(
        "/v1/properties", headers={"Origin": "http://localhost:5173"}
    )
    assert "access-control-allow-origin" not in response.headers


def test_settings_split_origins() -> None:
    assert Settings(cors_origins=" a, ,b ").cors_origin_list == ["a", "b"]


def test_state_is_per_app_instance(example: Example) -> None:
    first, second = TestClient(create_app()), TestClient(create_app())
    body = {k: v for k, v in example("student", "profile").items() if k != "id"}
    created = first.post("/v1/profiles", json=body).json()
    assert second.get(f"/v1/profiles/{created['id']}").status_code == 404
