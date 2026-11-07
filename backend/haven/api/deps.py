"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request

from haven.api.backend import Backend


def get_backend(request: Request) -> Backend:
    backend: Backend = request.app.state.backend
    return backend


BackendDep = Annotated[Backend, Depends(get_backend)]
