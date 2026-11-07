"""RFC 9457 problem+json errors: exceptions, handlers and OpenAPI response docs."""

import json
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from haven.api.schemas import FieldError, ProblemDetail
from haven.config import CONTRACT_EXAMPLES_DIR

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ApiError(Exception):
    """An error a backend raises; rendered as problem+json."""

    status: int = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(ApiError):
    status = 404

    def __init__(self, kind: str, id: str) -> None:
        super().__init__(f"No {kind} with id '{id}'.")


class NotAvailable(ApiError):
    """The current backend can't answer this request (e.g. no fixture for it)."""

    status = 501


def problem_response(problem: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def _problem(status: int, request: Request, detail: str | None, **extra: Any) -> JSONResponse:
    return problem_response(
        ProblemDetail(
            title=HTTPStatus(status).phrase,
            status=status,
            detail=detail,
            instance=request.url.path,
            **extra,
        )
    )


async def _api_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return _problem(exc.status, request, exc.detail)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail if isinstance(exc.detail, str) else None
    return _problem(exc.status_code, request, detail)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        FieldError(loc=list(e.get("loc", ())), msg=str(e.get("msg", "")), type=str(e.get("type")))
        for e in exc.errors()
    ]
    return _problem(422, request, "The request failed validation.", errors=errors)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)


# --- OpenAPI documentation -------------------------------------------------------------

PROBLEM_REF = {"$ref": "#/components/schemas/ProblemDetail"}


def _error_example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (CONTRACT_EXAMPLES_DIR / "errors" / f"{name}.json").read_text(encoding="utf-8")
    )
    return data


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """``responses=`` entries documenting problem+json errors for the given statuses."""
    descriptions = {
        404: "The resource does not exist.",
        422: "The request failed validation.",
        501: "The current backend has no data for this request (fixture backend).",
    }
    examples = {404: "not_found", 422: "validation_error"}
    out: dict[int | str, dict[str, Any]] = {}
    for status in statuses:
        media: dict[str, Any] = {"schema": PROBLEM_REF}
        if status in examples:
            media["example"] = _error_example(examples[status])
        out[status] = {
            "description": descriptions[status],
            "content": {PROBLEM_MEDIA_TYPE: media},
        }
    return out
