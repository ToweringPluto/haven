"""Every /v1 route documents a response model, a summary, examples and problem+json errors."""

from typing import Any

import pytest
from fastapi.routing import APIRoute

from haven.api.app import create_app
from haven.api.routes import (
    account,
    assist,
    data_sources,
    meta,
    profiles,
    properties,
    reports,
    uploads,
)
from haven.api.schemas import ProfileInput
from haven.domain import RenterProfile

APP = create_app()
SPEC: dict[str, Any] = APP.openapi()
# FastAPI 0.162 includes routers lazily (app.routes holds an internal wrapper), so read the
# APIRoutes from the routers that define them.
ROUTERS = [
    profiles.router,
    properties.router,
    uploads.router,
    reports.assessments,
    reports.reports,
    meta.router,
    data_sources.router,
    account.router,
    assist.router,
]
V1_ROUTES = [r for router in ROUTERS for r in router.routes if isinstance(r, APIRoute)]
OPERATIONS = [
    (path, method, op)
    for path, item in SPEC["paths"].items()
    if path.startswith("/v1")
    for method, op in item.items()
]

EXPECTED = {
    ("POST", "/v1/profiles"),
    ("GET", "/v1/profiles"),
    ("GET", "/v1/profiles/{profile_id}"),
    ("PUT", "/v1/profiles/{profile_id}"),
    ("DELETE", "/v1/profiles/{profile_id}"),
    ("GET", "/v1/properties"),
    ("GET", "/v1/properties/{property_id}"),
    ("POST", "/v1/properties/{property_id}/cost"),
    ("POST", "/v1/properties/{property_id}/suitability"),
    ("POST", "/v1/uploads"),
    ("GET", "/v1/uploads"),
    ("DELETE", "/v1/uploads/{upload_id}"),
    ("POST", "/v1/assessments"),
    ("GET", "/v1/reports"),
    ("GET", "/v1/reports/{report_id}"),
    ("GET", "/v1/meta/enums"),
    ("GET", "/v1/data-sources"),
    ("GET", "/v1/me"),
    ("DELETE", "/v1/me"),
    ("GET", "/v1/me/saved-homes"),
    ("PUT", "/v1/me/saved-homes"),
    ("POST", "/v1/photo-screen"),
    ("POST", "/v1/read-aloud"),
}
# Operations whose success response is a documented binary body rather than JSON.
BINARY_RESPONSES = {("POST", "/v1/read-aloud"): "audio/mpeg"}


def test_all_expected_routes_exist() -> None:
    found = {(m.upper(), p) for p, item in SPEC["paths"].items() if p != "/healthz" for m in item}
    assert found == EXPECTED
    assert len(V1_ROUTES) == len(EXPECTED)


@pytest.mark.parametrize("route", V1_ROUTES, ids=lambda r: f"{sorted(r.methods)[0]} {r.path}")
def test_route_has_summary_and_response_model(route: APIRoute) -> None:
    assert route.summary
    if (sorted(route.methods)[0], "/v1" + route.path) in BINARY_RESPONSES:
        return
    if route.status_code != 204:
        assert route.response_model is not None


@pytest.mark.parametrize("path,method,op", OPERATIONS, ids=lambda x: str(x)[:40])
def test_operation_documents_examples(path: str, method: str, op: dict[str, Any]) -> None:
    success = [code for code in op["responses"] if code.startswith("2")]
    assert len(success) == 1
    code = success[0]
    binary = BINARY_RESPONSES.get((method.upper(), path))
    if binary:
        assert list(op["responses"][code]["content"]) == [binary]
    elif code != "204":
        media = op["responses"][code]["content"]["application/json"]
        assert media.get("examples"), f"{method} {path}: no response examples"
    body = op.get("requestBody", {}).get("content", {})
    if "application/json" in body:
        assert body["application/json"].get("examples"), f"{method} {path}: no request examples"


@pytest.mark.parametrize("path,method,op", OPERATIONS, ids=lambda x: str(x)[:40])
def test_errors_are_problem_json(path: str, method: str, op: dict[str, Any]) -> None:
    for code, response in op["responses"].items():
        if code.startswith(("4", "5")):
            assert list(response["content"]) == ["application/problem+json"]
            schema = response["content"]["application/problem+json"]["schema"]
            assert schema == {"$ref": "#/components/schemas/ProblemDetail"}


def test_problem_detail_component_is_registered() -> None:
    components = SPEC["components"]["schemas"]
    assert "ProblemDetail" in components and "FieldError" in components
    assert "HTTPValidationError" not in components


@pytest.mark.parametrize("input_model,model", [(ProfileInput, RenterProfile)])
def test_input_models_match_domain_models(input_model: Any, model: Any) -> None:
    """Request bodies are the domain model without the server-assigned id."""
    expected = {k: v for k, v in model.model_fields.items() if k != "id"}
    assert list(input_model.model_fields) == list(expected)
    for name, field in expected.items():
        assert input_model.model_fields[name].annotation == field.annotation, name
