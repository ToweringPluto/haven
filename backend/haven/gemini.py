"""A thin JSON-only wrapper around the Google Gemini API.

Haven uses Gemini in two places: photo screening (:mod:`haven.screening.gemini`) and,
optionally, rewording report sentences (:mod:`haven.explain.gemini_wording`). Both go through
:class:`JsonModel`, so tests swap in a fake and never call the network or need a key.

Every failure (no network, quota, a blocked or malformed response) becomes
:class:`GeminiError`; callers decide whether that means "can't tell" or a 503. Never log the
API key, the image or the full response.
"""

import json
import logging
from typing import Any, Protocol

from haven.config import Settings

logger = logging.getLogger(__name__)


class GeminiError(RuntimeError):
    """Gemini couldn't give a usable answer."""


class JsonModel(Protocol):
    """A model that answers a prompt (plus an optional image) with JSON matching a schema."""

    model: str

    def generate_json(
        self, *, prompt: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None
    ) -> Any:
        """The parsed JSON answer. ``image`` is ``(bytes, mime type)``. Raises GeminiError."""
        ...


class GoogleGemini:
    """:class:`JsonModel` backed by the ``google-genai`` SDK."""

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        from google import genai
        from google.genai import types

        self.model = model
        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
        )

    def generate_json(
        self, *, prompt: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None
    ) -> Any:
        types = self._types
        contents: list[Any] = []
        if image is not None:
            data, mime_type = image
            contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        contents.append(prompt)
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=schema,
                    temperature=0,
                ),
            )
            text = response.text
        except Exception as exc:  # noqa: BLE001 - any SDK/network failure is a GeminiError
            logger.warning("Gemini request failed: %s", type(exc).__name__)
            raise GeminiError(f"Gemini request failed ({type(exc).__name__}).") from exc
        if not text:
            raise GeminiError("Gemini returned an empty or blocked response.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiError("Gemini's response wasn't valid JSON.") from exc


def make_gemini(settings: Settings) -> GoogleGemini | None:
    """A Gemini client when an API key is configured, otherwise ``None``."""
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        return None
    return GoogleGemini(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
