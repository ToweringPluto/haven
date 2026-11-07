"""FastAPI application factory."""

from fastapi import FastAPI
from pydantic import BaseModel

from haven import __version__


class Health(BaseModel):
    status: str


def create_app() -> FastAPI:
    app = FastAPI(title="Haven API", version=__version__)

    @app.get("/healthz", response_model=Health, summary="Liveness check")
    def healthz() -> Health:
        return Health(status="ok")

    return app
