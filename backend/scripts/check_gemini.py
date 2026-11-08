"""Check that photo screening with Google Gemini is set up correctly.

Reads the same settings as the API (``backend/.env`` plus ``HAVEN_*`` environment variables),
then:

1. confirms ``HAVEN_VISION_PROVIDER=gemini`` and ``HAVEN_GEMINI_API_KEY`` are set;
2. confirms the key works and ``HAVEN_GEMINI_MODEL`` exists (lists the models it can use if not);
3. sends one small JSON request, the same kind photo screening makes;
4. with a photo path, runs that photo through the real screening pipeline (quality gate first,
   then Gemini) and prints the signals, exactly as ``POST /v1/photo-screen`` would.

Never prints the key. Usage (from ``backend/``)::

    uv run poe check-gemini
    uv run poe check-gemini path/to/photo.jpg
"""

from __future__ import annotations

import sys
from pathlib import Path

from haven.config import ENV_FILE, Settings
from haven.gemini import GeminiError, GoogleGemini, make_gemini
from haven.screening.screeners import ScreeningPipeline, make_screener


def fail(message: str) -> int:
    print(f"FAIL  {message}")
    return 1


def ok(message: str) -> None:
    print(f"OK    {message}")


def check_model(model: GoogleGemini) -> bool:
    client = model._client
    try:
        client.models.get(model=model.model)
    except Exception as exc:  # noqa: BLE001 - report any SDK/network failure to the user
        print(f"FAIL  Couldn't use model {model.model!r} ({type(exc).__name__}: {exc}).")
        print("      If this is an auth error, the key is wrong or the Gemini API isn't enabled.")
        try:
            names = sorted(
                (m.name or "").removeprefix("models/")
                for m in client.models.list()
                if "generateContent" in (getattr(m, "supported_actions", None) or [])
            )
        except Exception:  # noqa: BLE001
            return False
        flash = [n for n in names if "flash" in n] or names
        print("      Models this key can use (set one as HAVEN_GEMINI_MODEL):")
        for name in flash[:15]:
            print(f"        {name}")
        return False
    ok(f"Model {model.model!r} is available to this key.")
    return True


def main(argv: list[str]) -> int:
    settings = Settings()
    print(f"Settings file: {ENV_FILE} ({'found' if ENV_FILE.exists() else 'not found'})")

    if (settings.vision_provider or "").lower() != "gemini":
        return fail("HAVEN_VISION_PROVIDER isn't \"gemini\", so photos won't be screened.")
    ok("HAVEN_VISION_PROVIDER=gemini")

    model = make_gemini(settings)
    if model is None:
        return fail("HAVEN_GEMINI_API_KEY is empty. Paste your Google AI Studio key into it.")
    ok("HAVEN_GEMINI_API_KEY is set.")

    if not check_model(model):
        return 1

    try:
        answer = model.generate_json(
            prompt='Reply with {"ready": true}.',
            schema={
                "type": "object",
                "properties": {"ready": {"type": "boolean"}},
                "required": ["ready"],
            },
        )
    except GeminiError as exc:
        return fail(f"Test request failed: {exc} Check the key's quota and billing.")
    if not (isinstance(answer, dict) and answer.get("ready") is True):
        return fail(f"Unexpected test answer: {answer!r}")
    ok("Test JSON request succeeded.")

    if argv:
        photo = Path(argv[0])
        pipeline = ScreeningPipeline(make_screener(settings), settings.quality)
        try:
            result = pipeline.run(photo.read_bytes())
        except GeminiError as exc:
            return fail(f"Screening {photo} failed: {exc}")
        print(f"\nPhoto: {photo}  (evidence quality: {result.quality.quality.value})")
        for signal in result.signals:
            print(f"  {signal.kind.value:<15} {signal.likelihood.value:<22} {signal.note}")

    print("\nGemini photo screening is ready. Restart the API to pick up .env changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
