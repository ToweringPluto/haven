"""FastAPI application factory."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

from haven import __version__
from haven.api.backend import Backend
from haven.api.errors import install_error_handlers
from haven.api.fixtures import FixtureBackend
from haven.api.routes import v1
from haven.api.schemas import ProblemDetail
from haven.config import Settings


class Health(BaseModel):
    status: str


def _install_openapi(app: FastAPI) -> None:
    """Add ProblemDetail to the components: error responses reference it by $ref under
    ``application/problem+json``, which FastAPI doesn't register on its own."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            problem = ProblemDetail.model_json_schema(
                ref_template="#/components/schemas/{model}", mode="serialization"
            )
            components = schema.setdefault("components", {}).setdefault("schemas", {})
            components.update(problem.pop("$defs", {}))
            components["ProblemDetail"] = problem
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]


def create_app(settings: Settings | None = None, backend: Backend | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="Haven API",
        version=__version__,
        description="Decision support for Edinburgh renters. Prototype: assessments are "
        "indicative, not a legal, safety, accessibility or compliance certification.",
    )
    app.state.backend = backend if backend is not None else FixtureBackend(settings.fixtures_dir)

    origins = settings.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_error_handlers(app)

    @app.get("/healthz", response_model=Health, summary="Liveness check")
    def healthz() -> Health:
        return Health(status="ok")

    app.include_router(v1)
    _install_openapi(app)
    return app
