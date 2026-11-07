"""FastAPI application factory."""

from typing import Any

from fastapi import FastAPI, routing
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from pydantic import BaseModel

from haven import __version__
from haven.api.auth import make_jwks_client
from haven.api.backend import Backend
from haven.api.engines import EngineBackend
from haven.api.errors import install_error_handlers
from haven.api.fixtures import FixtureBackend
from haven.api.rate_limit import SlidingWindowRateLimiter
from haven.api.routes import v1
from haven.api.schemas import ProblemDetail
from haven.config import Settings
from haven.store import load_seed


class Health(BaseModel):
    status: str


def _restore_examples(app: FastAPI, schema: dict[str, Any]) -> None:
    """Put the declared examples back verbatim.

    ``get_openapi`` encodes the whole document with ``exclude_none=True``, which also strips
    ``null`` values out of example payloads (e.g. ``"value": null`` on insufficient
    evidence), so the published examples would no longer match their own schemas.
    """
    for ctx in routing.iter_route_contexts(app.routes):
        route = ctx.original_route
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        item = schema["paths"].get(ctx.path_format, {})
        for method in ctx.methods or ():
            op = item.get(method.lower())
            if op is None:
                continue
            for status, response in (route.responses or {}).items():
                for media_type, media in response.get("content", {}).items():
                    if "examples" in media:
                        target = op["responses"][str(status)]["content"][media_type]
                        target["examples"] = jsonable_encoder(media["examples"])
            info = route.body_field.field_info if route.body_field else None
            examples = getattr(info, "openapi_examples", None)
            if examples and "requestBody" in op:
                for media in op["requestBody"]["content"].values():
                    media["examples"] = jsonable_encoder(examples)


def _install_openapi(app: FastAPI) -> None:
    """Add ProblemDetail to the components: error responses reference it by $ref under
    ``application/problem+json``, which FastAPI doesn't register on its own. Also keeps
    ``null`` values in examples (see ``_restore_examples``)."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            _restore_examples(app, schema)
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
    app.state.settings = settings
    if backend is None:
        backend = (
            FixtureBackend(settings.fixtures_dir)
            if settings.backend == "fixtures"
            else EngineBackend(settings.fixtures_dir, seed=load_seed(settings.seed_path))
        )
    app.state.backend = backend
    app.state.jwks_client = make_jwks_client(settings)
    window = settings.rate_limit_window_seconds
    app.state.rate_limiters = {
        "photo_screen": SlidingWindowRateLimiter(settings.photo_screen_rate_limit, window),
        "read_aloud": SlidingWindowRateLimiter(settings.read_aloud_rate_limit, window),
    }

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
