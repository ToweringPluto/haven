"""GeminiScreener with a fake model: mapping, wording guard, failures, and the quality gate."""

from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageFilter
from pydantic import SecretStr

from haven.config import Settings
from haven.domain import EvidenceQuality, Likelihood, SignalKind
from haven.explain import certainty_phrases
from haven.gemini import GeminiError
from haven.screening import NullScreener, ScreeningPipeline, make_screener
from haven.screening.gemini import SCHEMA, GeminiScreener


def photo(blur: float = 0) -> Image.Image:
    rng = np.random.default_rng(3)
    blocks = rng.integers(60, 200, size=(96, 128), dtype=np.uint8)
    image = Image.fromarray(np.kron(blocks, np.ones((8, 8), dtype=np.uint8))).convert("RGB")
    return image.filter(ImageFilter.GaussianBlur(blur)) if blur else image


class FakeGemini:
    model = "gemini-test"

    def __init__(self, answer: Any = None, error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate_json(
        self, *, prompt: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None
    ) -> Any:
        self.calls.append({"prompt": prompt, "schema": schema, "image": image})
        if self.error is not None:
            raise self.error
        return self.answer


def answer(**ratings: tuple[str, str]) -> dict[str, Any]:
    return {k: {"likelihood": r, "what_is_visible": v} for k, (r, v) in ratings.items()}


FULL = answer(
    possible_damp=("possible", "Faint tide marks below the window"),
    possible_mould=("likely", "Dark spotting in the ceiling corner"),
    entrance_step=("insufficient_evidence", "The entrance isn't shown"),
)


def run(model: FakeGemini, image: Image.Image | None = None) -> dict[SignalKind, Any]:
    result = ScreeningPipeline(GeminiScreener(model)).run(image or photo(), upload_id="u1")
    return {s.kind: s for s in result.signals}


def test_ratings_map_to_signals_without_confidence() -> None:
    model = FakeGemini(FULL)
    signals = run(model)
    assert signals[SignalKind.possible_damp].likelihood is Likelihood.possible
    assert signals[SignalKind.possible_mould].likelihood is Likelihood.likely
    assert signals[SignalKind.entrance_step].likelihood is Likelihood.insufficient_evidence
    for s in signals.values():
        assert s.confidence is None
        assert s.source == "Gemini (gemini-test)"
        assert s.id == f"u1:{s.kind.value}"
        assert s.evidence_quality is EvidenceQuality.good
    assert "tide marks" in (signals[SignalKind.possible_damp].note or "")
    call = model.calls[0]
    assert call["schema"] is SCHEMA
    assert call["image"][1] == "image/jpeg"


def test_certainty_wording_from_the_model_is_dropped() -> None:
    model = FakeGemini(
        answer(
            possible_damp=("likely", "This flat has damp, definitely"),
            possible_mould=("unlikely", "The wall is clean"),
            entrance_step=("possible", "A raised threshold"),
        )
    )
    for signal in run(model).values():
        assert certainty_phrases(signal.note or "") == [], signal.note
    assert "has damp" not in (run(model)[SignalKind.possible_damp].note or "")


@pytest.mark.parametrize(
    "bad",
    [None, "not json", [], {"possible_damp": {"likelihood": "certain"}}, {"possible_damp": 3}],
)
def test_missing_or_bad_ratings_become_insufficient(bad: Any) -> None:
    signals = run(FakeGemini(bad))
    assert len(signals) == 3
    for s in signals.values():
        assert s.likelihood is Likelihood.insufficient_evidence
        assert s.confidence is None


def test_poor_photo_never_reaches_gemini() -> None:
    model = FakeGemini(FULL)
    signals = run(model, photo(blur=12))
    assert model.calls == []
    assert all(s.likelihood is Likelihood.insufficient_evidence for s in signals.values())


def test_request_errors_propagate_for_the_caller_to_handle() -> None:
    with pytest.raises(GeminiError):
        run(FakeGemini(error=GeminiError("quota")))


def test_make_screener_needs_a_key_for_gemini() -> None:
    assert isinstance(make_screener(Settings(vision_provider="gemini")), NullScreener)
    screener = make_screener(
        Settings(vision_provider="gemini", gemini_api_key=SecretStr("k"), gemini_model="m")
    )
    assert isinstance(screener, GeminiScreener)
    assert screener.name == "Gemini (m)"
