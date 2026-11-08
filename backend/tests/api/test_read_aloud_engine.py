"""Engine backend read-aloud: Gemini speech (faked), 501 when unconfigured, 503 on failure."""

import io
import time
import wave

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from haven.api.app import create_app
from haven.api.engines import EngineBackend
from haven.config import CONTRACT_EXAMPLES_DIR, Settings
from haven.speech import SpeechError, SpeechModel, make_speech, pcm_to_wav, sample_rate_from_mime

DOMAIN = "haven-test.eu.auth0.com"
AUDIENCE = "https://api.haven.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _Key:
    key = KEY.public_key()


class FakeJWKS:
    def get_signing_key_from_jwt(self, token: str) -> _Key:
        return _Key()


class FakeSpeech:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.spoken: list[str] = []

    def speak(self, text: str) -> bytes:
        if self.error:
            raise self.error
        self.spoken.append(text)
        return pcm_to_wav(b"\x00\x00" * 240)


def token() -> str:
    now = int(time.time())
    claims = {"sub": "auth0|u1", "aud": AUDIENCE, "iss": f"https://{DOMAIN}/", "iat": now}
    return jwt.encode(claims | {"exp": now + 600}, KEY, algorithm="RS256")


def client_for(speech: SpeechModel | None) -> TestClient:
    settings = Settings(auth0_domain=DOMAIN, auth0_audience=AUDIENCE, read_aloud_provider=None)
    backend = EngineBackend(CONTRACT_EXAMPLES_DIR, settings=settings, speech=speech)
    app = create_app(settings, backend=backend)
    app.state.jwks_client = FakeJWKS()
    return TestClient(app)


def read(client: TestClient, text: str = "Hello there") -> object:
    return client.post(
        "/v1/read-aloud", json={"text": text}, headers={"Authorization": f"Bearer {token()}"}
    )


def test_speech_service_returns_playable_wav() -> None:
    speech = FakeSpeech()
    res = read(client_for(speech))
    assert res.status_code == 200  # type: ignore[attr-defined]
    assert res.headers["content-type"] == "audio/wav"  # type: ignore[attr-defined]
    with wave.open(io.BytesIO(res.content)) as audio:  # type: ignore[attr-defined]
        assert audio.getframerate() == 24_000
        assert audio.getnchannels() == 1
    assert speech.spoken == ["Hello there"]


def test_no_speech_service_is_501() -> None:
    res = read(client_for(None))
    assert res.status_code == 501  # type: ignore[attr-defined]


def test_speech_failure_is_503() -> None:
    res = read(client_for(FakeSpeech(SpeechError("quota"))))
    assert res.status_code == 503  # type: ignore[attr-defined]


def test_make_speech_needs_provider_and_key() -> None:
    assert make_speech(Settings(read_aloud_provider=None, gemini_api_key="k")) is None
    assert make_speech(Settings(read_aloud_provider="gemini", gemini_api_key=None)) is None
    assert make_speech(Settings(read_aloud_provider="", gemini_api_key="k")) is None


@pytest.mark.parametrize(
    ("mime", "rate"),
    [("audio/L16;codec=pcm;rate=16000", 16_000), ("audio/L16", 24_000), (None, 24_000)],
)
def test_sample_rate_from_mime(mime: str | None, rate: int) -> None:
    assert sample_rate_from_mime(mime) == rate
