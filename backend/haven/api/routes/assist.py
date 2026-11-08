"""Signed-in assistive features: photo screening and read-aloud.

Both are per-user rate limited. Photos are read into memory with a hard size cap and never
written anywhere: the body is the raw image (not multipart, whose parser spools files over
1 MB to a temporary file on disk).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request, Response

from haven.api import examples as ex
from haven.api.deps import BackendDep
from haven.api.errors import PayloadTooLarge, UnsupportedMediaType, problem_responses
from haven.api.rate_limit import PhotoScreenUser, ReadAloudUser
from haven.api.schemas import PhotoScreen, ReadAloudRequest
from haven.config import Settings

router = APIRouter(tags=["assist"])

IMAGE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),  # plus "WEBP" at offset 8, checked below
}
BINARY = {"type": "string", "format": "binary"}
WAV_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "WAV audio (16-bit mono PCM).",
        "content": {"audio/wav": {"schema": BINARY}},
    }
}


def _matches_signature(content_type: str, data: bytes) -> bool:
    if not data.startswith(IMAGE_SIGNATURES[content_type]):
        return False
    return content_type != "image/webp" or data[8:12] == b"WEBP"


async def _read_capped(request: Request, max_bytes: int) -> bytes:
    """Read the body into memory, refusing (early, where possible) anything over the cap."""
    too_large = PayloadTooLarge(f"Images must be {max_bytes // (1024 * 1024)} MB or smaller.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise too_large
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise too_large
    return bytes(buffer)


@router.post(
    "/photo-screen",
    response_model=PhotoScreen,
    summary="Screen a photo for possible issues (signed in)",
    description="Send one JPG, PNG or WebP image as the raw request body with a matching "
    "`Content-Type` (max `HAVEN_PHOTO_SCREEN_MAX_BYTES`, default 5 MB). The image is processed "
    "in memory and never stored. Signals are possibilities to inspect, never diagnoses. "
    "Rate limited per user (`HAVEN_PHOTO_SCREEN_RATE_LIMIT` per "
    "`HAVEN_RATE_LIMIT_WINDOW_SECONDS`). The fixture backend returns 501.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {media: {"schema": BINARY} for media in IMAGE_SIGNATURES},
        }
    },
    responses=ex.json_response(200, ex.photo_screen_examples())
    | problem_responses(401, 413, 415, 429, 501, 503),
)
async def photo_screen(request: Request, user: PhotoScreenUser, backend: BackendDep) -> PhotoScreen:
    settings: Settings = request.app.state.settings
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in IMAGE_SIGNATURES:
        raise UnsupportedMediaType("Send a JPG, PNG or WebP image as the request body.")

    content = await _read_capped(request, settings.photo_screen_max_bytes)
    if not _matches_signature(content_type, content):
        raise UnsupportedMediaType(f"The body isn't a valid {content_type} image.")
    return backend.screen_photo(content=content, content_type=content_type)


@router.post(
    "/read-aloud",
    response_class=Response,
    summary="Read text aloud (signed in)",
    description="Returns WAV audio of the text (max `HAVEN_READ_ALOUD_MAX_CHARS` characters, "
    "default 5000), spoken by Google Gemini when `HAVEN_READ_ALOUD_PROVIDER=gemini`; the text "
    "is sent to Google and not stored. `501` when no speech service is configured (clients "
    "can fall back to the browser's own voice), `503` if the service fails. Rate limited per "
    "user (`HAVEN_READ_ALOUD_RATE_LIMIT` per `HAVEN_RATE_LIMIT_WINDOW_SECONDS`).",
    responses=WAV_RESPONSE | problem_responses(401, 413, 422, 429, 501, 503),
)
def read_aloud(
    request: Request,
    user: ReadAloudUser,
    backend: BackendDep,
    body: Annotated[ReadAloudRequest, Body(openapi_examples=ex.read_aloud_examples())],
) -> Response:
    settings: Settings = request.app.state.settings
    if len(body.text) > settings.read_aloud_max_chars:
        raise PayloadTooLarge(f"Text must be {settings.read_aloud_max_chars} characters or fewer.")
    return Response(content=backend.read_aloud(body.text), media_type="audio/wav")
