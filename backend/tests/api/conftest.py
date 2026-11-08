import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.fixtures import FixtureBackend
from haven.config import CONTRACT_EXAMPLES_DIR
from tests.api.auth_helpers import signed_in

type Example = Callable[[str, str], Any]


@pytest.fixture
def client() -> TestClient:
    """The default (engine) backend, signed in as :data:`USER`."""
    return signed_in()


@pytest.fixture
def anon_client() -> TestClient:
    """The default backend with nobody signed in (and sign-in not configured)."""
    return TestClient(create_app())


@pytest.fixture
def fixture_client() -> TestClient:
    """The fixtures-only backend (``HAVEN_BACKEND=fixtures``), signed in as :data:`USER`."""
    return signed_in(FixtureBackend(CONTRACT_EXAMPLES_DIR))


@pytest.fixture
def example() -> Example:
    def load(persona: str, stem: str) -> Any:
        path = CONTRACT_EXAMPLES_DIR / persona / f"{stem}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return load
