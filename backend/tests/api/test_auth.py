"""Auth0 bearer-token verification and the signed-in endpoints (/v1/me, photo-screen,
read-aloud). Tokens are signed with a throwaway RSA key standing in for the tenant's JWKS."""

import logging
import time
from dataclasses import dataclass
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.fixtures import FixtureBackend
from haven.api.rate_limit import SlidingWindowRateLimiter
from haven.api.schemas import PhotoScreen
from haven.config import CONTRACT_EXAMPLES_DIR, Settings
from haven.domain import EvidenceQuality

DOMAIN = "haven-test.eu.auth0.com"
AUDIENCE = "https://api.haven.test"
EMAIL_CLAIM = "https://haven.test/email"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@dataclass
class _SigningKey:
    key: Any


class FakeJWKS:
    """Stands in for PyJWKClient: always returns our test public key."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def get_signing_key_from_jwt(self, token: str) -> _SigningKey:
        if self.error:
            raise self.error
        jwt.get_unverified_header(token)  # malformed tokens fail here, like the real client
        return _SigningKey(PRIVATE_KEY.public_key())


class FakeBackend(FixtureBackend):
    def __init__(self) -> None:
        super().__init__(CONTRACT_EXAMPLES_DIR)
        self.screened: list[int] = []

    def screen_photo(self, *, content: bytes, content_type: str) -> PhotoScreen:
        self.screened.append(len(content))
        return PhotoScreen(evidence_quality=EvidenceQuality.good, signals=[])

    def read_aloud(self, text: str) -> bytes:
        return b"ID3fake-mp3"


def token(key: rsa.RSAPrivateKey = PRIVATE_KEY, algorithm: str = "RS256", **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": f"https://{DOMAIN}/",
        "aud": AUDIENCE,
        "sub": "auth0|user-1",
        "iat": now,
        "exp": now + 600,
        EMAIL_CLAIM: "renter@example.com",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    signing_key: Any = "not-the-rsa-key" if algorithm == "HS256" else key
    return jwt.encode(claims, signing_key, algorithm=algorithm)


def auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def make_client(backend: FixtureBackend | None = None, **settings: Any) -> TestClient:
    defaults: dict[str, Any] = {
        "auth0_domain": DOMAIN,
        "auth0_audience": AUDIENCE,
        "auth0_email_claim": EMAIL_CLAIM,
    }
    app = create_app(Settings(**(defaults | settings)), backend=backend)
    if app.state.jwks_client is not None:
        app.state.jwks_client = FakeJWKS()
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return make_client(FakeBackend())


# --- /v1/me and token verification ------------------------------------------------------


def test_me_returns_verified_claims(client: TestClient) -> None:
    res = client.get("/v1/me", headers=auth(token()))
    assert res.status_code == 200
    assert res.json() == {"sub": "auth0|user-1", "email": "renter@example.com"}


def test_me_email_is_null_without_the_claim(client: TestClient) -> None:
    res = client.get("/v1/me", headers=auth(token(**{EMAIL_CLAIM: None})))
    assert res.json() == {"sub": "auth0|user-1", "email": None}


def test_missing_token_is_401_problem_json(client: TestClient) -> None:
    res = client.get("/v1/me")
    assert res.status_code == 401
    assert res.headers["content-type"] == "application/problem+json"
    assert res.headers["www-authenticate"] == "Bearer"
    assert res.json()["detail"] == "Sign in to use this feature."


@pytest.mark.parametrize(
    "bad_token",
    [
        pytest.param(token(aud="https://someone-else"), id="wrong-audience"),
        pytest.param(token(iss="https://evil.example/"), id="wrong-issuer"),
        pytest.param(token(exp=int(time.time()) - 3600), id="expired"),
        pytest.param(token(key=OTHER_KEY), id="wrong-signing-key"),
        pytest.param(token(algorithm="HS256"), id="hs256-not-allowed"),
        pytest.param(token(sub=None), id="missing-sub"),
        pytest.param("not-a-jwt", id="malformed"),
    ],
)
def test_invalid_tokens_are_401(client: TestClient, bad_token: str) -> None:
    res = client.get("/v1/me", headers=auth(bad_token))
    assert res.status_code == 401


def test_rejected_tokens_are_never_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    bad = token(aud="https://someone-else")
    with caplog.at_level(logging.DEBUG):
        client.get("/v1/me", headers=auth(bad))
    assert bad not in caplog.text
    assert bad.split(".")[1] not in caplog.text  # nor the claims segment


def test_auth_not_configured_is_503_and_public_routes_still_work() -> None:
    client = make_client(auth0_domain="", auth0_audience="")
    assert client.get("/v1/me", headers=auth(token())).status_code == 503
    assert client.get("/v1/properties").status_code == 200
    assert client.get("/healthz").status_code == 200


def test_jwks_unreachable_is_503(client: TestClient) -> None:
    client.app.state.jwks_client = FakeJWKS(error=jwt.PyJWKClientConnectionError("down"))  # type: ignore[attr-defined]
    assert client.get("/v1/me", headers=auth(token())).status_code == 503


# --- POST /v1/photo-screen ----------------------------------------------------------------


def screen(client: TestClient, body: bytes, content_type: str = "image/jpeg", **kw: Any) -> Any:
    headers = {"Content-Type": content_type, **auth(kw.pop("t", None) or token())}
    return client.post("/v1/photo-screen", content=body, headers=headers)


def test_photo_screen_requires_sign_in(client: TestClient) -> None:
    res = client.post("/v1/photo-screen", content=JPEG, headers={"Content-Type": "image/jpeg"})
    assert res.status_code == 401


def test_photo_screen_success(client: TestClient) -> None:
    res = screen(client, PNG, "image/png")
    assert res.status_code == 200
    assert res.json() == {"evidence_quality": "good", "signals": []}


def test_photo_screen_on_fixture_backend_is_501() -> None:
    res = screen(make_client(FixtureBackend(CONTRACT_EXAMPLES_DIR)), JPEG)
    assert res.status_code == 501


def test_photo_screen_on_engine_backend_rejects_unreadable_image() -> None:
    # The signature matches, but the bytes aren't a decodable image.
    assert screen(make_client(), JPEG).status_code == 415


def test_photo_screen_rejects_oversized_images() -> None:
    backend = FakeBackend()
    client = make_client(backend, photo_screen_max_bytes=100)
    res = screen(client, JPEG + b"\x00" * 200)
    assert res.status_code == 413
    assert backend.screened == []


@pytest.mark.parametrize(
    "body,content_type",
    [
        pytest.param(JPEG, "image/gif", id="unsupported-type"),
        pytest.param(JPEG, "application/octet-stream", id="not-an-image-type"),
        pytest.param(b"<html>not an image</html>", "image/jpeg", id="content-mismatch"),
        pytest.param(b"RIFF\x00\x00\x00\x00WAVE", "image/webp", id="riff-but-not-webp"),
    ],
)
def test_photo_screen_rejects_non_images(
    client: TestClient, body: bytes, content_type: str
) -> None:
    assert screen(client, body, content_type).status_code == 415


def test_photo_screen_is_rate_limited_per_user() -> None:
    client = make_client(FakeBackend(), photo_screen_rate_limit=2)
    assert [screen(client, JPEG).status_code for _ in range(2)] == [200, 200]

    limited = screen(client, JPEG)
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0

    other_user = token(sub="auth0|user-2")
    assert screen(client, JPEG, t=other_user).status_code == 200


# --- POST /v1/read-aloud ------------------------------------------------------------------


def test_read_aloud_returns_audio(client: TestClient) -> None:
    res = client.post("/v1/read-aloud", json={"text": "Hello"}, headers=auth(token()))
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == b"ID3fake-mp3"


def test_read_aloud_rejects_long_and_blank_text() -> None:
    client = make_client(FakeBackend(), read_aloud_max_chars=10)
    too_long = client.post("/v1/read-aloud", json={"text": "x" * 11}, headers=auth(token()))
    assert too_long.status_code == 413
    blank = client.post("/v1/read-aloud", json={"text": "   "}, headers=auth(token()))
    assert blank.status_code == 422


def test_read_aloud_requires_sign_in(client: TestClient) -> None:
    assert client.post("/v1/read-aloud", json={"text": "Hello"}).status_code == 401


def test_read_aloud_on_fixture_backend_is_501() -> None:
    res = make_client().post("/v1/read-aloud", json={"text": "Hello"}, headers=auth(token()))
    assert res.status_code == 501


# --- Rate limiter --------------------------------------------------------------------------


def test_sliding_window_frees_slots_as_time_passes() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    limiter.hit("a")
    now[0] = 30
    limiter.hit("a")
    with pytest.raises(Exception, match="limit"):
        limiter.hit("a")
    now[0] = 61  # the first hit has left the window
    limiter.hit("a")
