"""Signed-in test clients: Auth0 verification bypassed (token checks live in test_auth)."""

from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.auth import get_current_user, get_optional_user
from haven.api.backend import Backend
from haven.api.schemas import CurrentUser

#: The signed-in user the ``client`` fixtures act as (token checks are tested in test_auth).
USER = CurrentUser(sub="auth0|test-user", email="renter@example.com")
OTHER_USER = CurrentUser(sub="auth0|someone-else", email=None)


def signed_in(backend: Backend | None = None, user: CurrentUser = USER) -> TestClient:
    """A client whose requests all come from ``user`` (Auth0 verification bypassed)."""
    app = create_app(backend=backend)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_optional_user] = lambda: user
    return TestClient(app)
