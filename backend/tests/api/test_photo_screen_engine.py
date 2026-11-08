"""Engine backend signed-in features: photo-screen (quality grade, Gemini or no model, 503)
and profiles owned by the signed-in user."""

import io
import time
from typing import Any

import jwt
import numpy as np
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from PIL import Image

from haven.api.app import create_app
from haven.api.engines import EngineBackend
from haven.config import CONTRACT_EXAMPLES_DIR, Settings
from haven.gemini import GeminiError
from haven.screening import NullScreener, Screener
from haven.screening.gemini import GeminiScreener

DOMAIN = "haven-test.eu.auth0.com"
AUDIENCE = "https://api.haven.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _Key:
    key = KEY.public_key()


class FakeJWKS:
    def get_signing_key_from_jwt(self, token: str) -> _Key:
        return _Key()


class FakeGemini:
    model = "gemini-test"

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def generate_json(
        self, *, prompt: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None
    ) -> Any:
        if self.error:
            raise self.error
        return {
            k: {"likelihood": "unlikely", "what_is_visible": "Clean"} for k in schema["required"]
        }


def token() -> str:
    now = int(time.time())
    claims = {"sub": "auth0|u1", "aud": AUDIENCE, "iss": f"https://{DOMAIN}/", "iat": now}
    return jwt.encode(claims | {"exp": now + 600}, KEY, algorithm="RS256")


def client_for(screener: Screener) -> TestClient:
    settings = Settings(auth0_domain=DOMAIN, auth0_audience=AUDIENCE)
    backend = EngineBackend(CONTRACT_EXAMPLES_DIR, screener=screener, settings=settings)
    app = create_app(settings, backend=backend)
    app.state.jwks_client = FakeJWKS()
    return TestClient(app)


def jpeg() -> bytes:
    rng = np.random.default_rng(3)
    blocks = rng.integers(60, 200, size=(96, 128), dtype=np.uint8)
    image = Image.fromarray(np.kron(blocks, np.ones((8, 8), dtype=np.uint8))).convert("RGB")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


def screen(client: TestClient) -> Any:
    headers = {"Content-Type": "image/jpeg", "Authorization": f"Bearer {token()}"}
    return client.post("/v1/photo-screen", content=jpeg(), headers=headers)


def test_no_model_still_grades_the_photo() -> None:
    response = screen(client_for(NullScreener()))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evidence_quality"] == "good"
    assert {s["likelihood"] for s in body["signals"]} == {"insufficient_evidence"}


def test_gemini_signals_are_returned() -> None:
    body = screen(client_for(GeminiScreener(FakeGemini()))).json()
    assert {s["likelihood"] for s in body["signals"]} == {"unlikely"}
    assert all(s["upload_id"] is None for s in body["signals"])


def test_gemini_failure_is_503() -> None:
    response = screen(client_for(GeminiScreener(FakeGemini(GeminiError("quota")))))
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")


# --- signed-in profiles (same token setup) -------------------------------------------------


def test_signed_in_profiles_are_listed_only_for_their_owner() -> None:
    client = client_for(NullScreener())
    auth = {"Authorization": f"Bearer {token()}"}
    mine = client.post("/v1/profiles", json={"label": "Mine"}, headers=auth).json()
    anonymous = client.post("/v1/profiles", json={"label": "Anon"}).json()

    listed = [p["id"] for p in client.get("/v1/profiles", headers=auth).json()["items"]]
    assert mine["id"] in listed and anonymous["id"] not in listed
    public = [p["id"] for p in client.get("/v1/profiles").json()["items"]]
    assert mine["id"] not in public


def test_invalid_token_on_profiles_is_401() -> None:
    client = client_for(NullScreener())
    response = client.get("/v1/profiles", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
