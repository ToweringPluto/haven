"""``GeminiScreener``: photo screening with Google Gemini (``HAVEN_VISION_PROVIDER=gemini``).

Gemini looks at one photo and rates each signal kind as ``likely``, ``possible``,
``unlikely`` or ``insufficient_evidence``, with a short description of what it can see.
What Haven keeps and what it drops:

* ``confidence`` is always ``None``: Gemini's ratings aren't calibrated probabilities.
* A description that uses certainty wording (``has damp``, ``is step-free``...) is dropped and
  replaced with a neutral one, so a signal never reads as a diagnosis.
* An answer that is missing a kind, or has an unknown rating, makes that kind
  ``insufficient_evidence``. Haven never guesses for the model.
* Request failures raise :class:`haven.gemini.GeminiError`; the caller decides whether that
  means "can't tell" (uploads) or a 503 (``/v1/photo-screen``).

The quality gate in :class:`ScreeningPipeline` runs first, so a ``poor`` photo never reaches
Gemini.
"""

import io
from typing import Any

from PIL import Image

from haven.domain import Likelihood, Signal, SignalKind
from haven.explain.language import certainty_phrases
from haven.gemini import JsonModel
from haven.screening.quality import QualityReport
from haven.screening.screeners import _WHAT_TO_CHECK, SIGNAL_KINDS, insufficient, signal_id

MAX_SIDE_PX = 1536
MAX_DESCRIPTION_CHARS = 240

_LABELS = {
    SignalKind.possible_damp: "signs of damp (staining, tide marks, peeling paint or plaster)",
    SignalKind.possible_mould: "signs of mould (black or green spotting, especially near "
    "windows, ceilings and corners)",
    SignalKind.entrance_step: "a step or steps at the entrance to the building or flat",
}

PROMPT = (
    "You are helping a renter in Edinburgh decide what to check at a viewing. Look at this "
    "property photo and, for each item below, rate how visible it is in THIS photo:\n"
    + "\n".join(f"- {kind.value}: {label}" for kind, label in _LABELS.items())
    + "\n\nRatings: 'likely' (clearly visible), 'possible' (some visual hints), 'unlikely' "
    "(the relevant area is visible and shows no sign of it), 'insufficient_evidence' (the "
    "relevant area isn't shown, or the photo can't tell). Prefer 'insufficient_evidence' "
    "over guessing. For each item, describe in one short sentence what you can see that "
    "led to the rating. Describe what is visible, never a diagnosis: say 'dark patches near "
    "the window frame', not 'the flat has mould'."
)

_RATINGS = [likelihood.value for likelihood in Likelihood]

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        kind.value: {
            "type": "object",
            "properties": {
                "likelihood": {"type": "string", "enum": _RATINGS},
                "what_is_visible": {"type": "string"},
            },
            "required": ["likelihood", "what_is_visible"],
        }
        for kind in SIGNAL_KINDS
    },
    "required": [kind.value for kind in SIGNAL_KINDS],
}


def _jpeg(image: Image.Image) -> bytes:
    """The photo as a JPEG no larger than MAX_SIDE_PX (smaller requests, same detail)."""
    copy = image.convert("RGB")
    copy.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
    buffer = io.BytesIO()
    copy.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def _description(raw: object, kind: SignalKind) -> str:
    text = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not text or certainty_phrases(text):
        return f"Gemini's rating for {kind.value.replace('_', ' ')} from this photo."
    if len(text) > MAX_DESCRIPTION_CHARS:
        text = text[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return text if text.endswith((".", "!", "?", "…")) else text + "."


class GeminiScreener:
    """:class:`haven.screening.Screener` backed by a Gemini :class:`JsonModel`."""

    def __init__(self, model: JsonModel) -> None:
        self.model = model
        self.name = f"Gemini ({model.model})"

    def screen(
        self, image: Image.Image, *, quality: QualityReport, upload_id: str | None
    ) -> list[Signal]:
        answer = self.model.generate_json(
            prompt=PROMPT, schema=SCHEMA, image=(_jpeg(image), "image/jpeg")
        )
        answer = answer if isinstance(answer, dict) else {}
        return [
            self._signal(kind, answer.get(kind.value), quality, upload_id) for kind in SIGNAL_KINDS
        ]

    def _signal(
        self, kind: SignalKind, item: object, quality: QualityReport, upload_id: str | None
    ) -> Signal:
        item = item if isinstance(item, dict) else {}
        rating = item.get("likelihood")
        if rating not in _RATINGS or rating == Likelihood.insufficient_evidence.value:
            why = (
                "Gemini couldn't tell from this photo."
                if rating == Likelihood.insufficient_evidence.value
                else "Gemini didn't give a usable rating for this photo."
            )
            return insufficient(
                kind, quality=quality.quality, upload_id=upload_id, source=self.name, why=why
            )
        likelihood = Likelihood(rating)
        seen = _description(item.get("what_is_visible"), kind)
        return Signal(
            id=signal_id(upload_id, kind),
            kind=kind,
            likelihood=likelihood,
            evidence_quality=quality.quality,
            confidence=None,
            upload_id=upload_id,
            source=self.name,
            note=f"Rated {likelihood.value} from the photo: {seen} {_WHAT_TO_CHECK[kind]}",
        )
