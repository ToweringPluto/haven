import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.fixtures import FixtureBackend
from haven.config import CONTRACT_EXAMPLES_DIR

type Example = Callable[[str, str], Any]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def fixture_client() -> TestClient:
    """The fixtures-only backend (``HAVEN_BACKEND=fixtures``)."""
    return TestClient(create_app(backend=FixtureBackend(CONTRACT_EXAMPLES_DIR)))


@pytest.fixture
def example() -> Example:
    def load(persona: str, stem: str) -> Any:
        path = CONTRACT_EXAMPLES_DIR / persona / f"{stem}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return load
