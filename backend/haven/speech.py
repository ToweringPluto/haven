"""Read-aloud: turn text into speech with Google Gemini's text-to-speech models.

Gemini returns raw 16-bit mono PCM; :func:`pcm_to_wav` wraps it in a WAV header (standard
library only, no audio encoder needed) so browsers can play it directly.

:class:`SpeechModel` is the seam tests use: they swap in a fake and never call the network or
need a key. Every failure becomes :class:`SpeechError`, which the API turns into a 503. Never
log the API key or the text.
"""

import io
import logging
import re
import wave
from typing import Any, Protocol

from haven.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 24_000


class SpeechError(RuntimeError):
    """The speech service couldn't produce audio."""


class SpeechModel(Protocol):
    """Something that reads text aloud and returns WAV audio."""

    def speak(self, text: str) -> bytes:
        """WAV audio of ``text``. Raises SpeechError."""
        ...


def pcm_to_wav(pcm: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> bytes:
    """Wrap 16-bit little-endian mono PCM in a WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(pcm)
    return buffer.getvalue()


def sample_rate_from_mime(mime_type: str | None) -> int:
    """The ``rate=`` parameter of a mime type such as ``audio/L16;codec=pcm;rate=24000``."""
    match = re.search(r"rate=(\d+)", mime_type or "")
    return int(match.group(1)) if match else DEFAULT_SAMPLE_RATE


class GeminiSpeech:
    """:class:`SpeechModel` backed by a Gemini text-to-speech model (``google-genai`` SDK)."""

    def __init__(self, *, api_key: str, model: str, voice: str, timeout_seconds: float) -> None:
        from google import genai
        from google.genai import types

        self.model = model
        self.voice = voice
        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
        )

    def speak(self, text: str) -> bytes:
        types = self._types
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=f"Read this aloud in a calm, clear voice:\n\n{text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)
                        )
                    ),
                ),
            )
            part: Any = response.candidates[0].content.parts[0]  # type: ignore[index,union-attr]
            data = part.inline_data.data
            mime_type = part.inline_data.mime_type
        except Exception as exc:  # noqa: BLE001 - any SDK/network/shape failure is a SpeechError
            logger.warning("Gemini speech request failed: %s", type(exc).__name__)
            raise SpeechError(f"Gemini speech request failed ({type(exc).__name__}).") from exc
        if not data:
            raise SpeechError("Gemini returned no audio.")
        if mime_type and "wav" in mime_type:
            return bytes(data)
        return pcm_to_wav(bytes(data), sample_rate_from_mime(mime_type))


def make_speech(settings: Settings) -> SpeechModel | None:
    """The configured speech service, or ``None`` when read-aloud isn't set up."""
    if settings.read_aloud_provider != "gemini":
        return None
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        logger.warning("HAVEN_READ_ALOUD_PROVIDER=gemini but HAVEN_GEMINI_API_KEY is not set.")
        return None
    return GeminiSpeech(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_tts_model,
        voice=settings.gemini_tts_voice,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
