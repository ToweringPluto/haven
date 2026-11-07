"""Screener protocol, NullScreener, VisionModelScreener slot and the gated pipeline."""

import io

import numpy as np
import pytest
from PIL import Image, ImageFilter

from haven.config import Settings
from haven.domain import EvidenceQuality, Likelihood, Signal, SignalKind
from haven.explain import BANNED_CERTAINTY_PHRASES, certainty_phrases
from haven.screening import (
    SIGNAL_KINDS,
    NotConfigured,
    NullScreener,
    QualityReport,
    ScreeningPipeline,
    VisionModelScreener,
    make_screener,
)


def photo(blur: float = 0) -> Image.Image:
    rng = np.random.default_rng(3)
    blocks = rng.integers(60, 200, size=(96, 128), dtype=np.uint8)
    image = Image.fromarray(np.kron(blocks, np.ones((8, 8), dtype=np.uint8))).convert("RGB")
    return image.filter(ImageFilter.GaussianBlur(blur)) if blur else image


class FakeScreener:
    """A model that 'sees' possible mould, to exercise the pipeline's non-poor path."""

    name = "Fake screener (tests)"

    def screen(
        self, image: Image.Image, *, quality: QualityReport, upload_id: str | None
    ) -> list[Signal]:
        return [
            Signal(
                id=f"{upload_id}:{k.value}",
                kind=k,
                likelihood=Likelihood.possible
                if k is SignalKind.possible_mould
                else Likelihood.unlikely,
                evidence_quality=quality.quality,
                source=self.name,
                note="Possible signal from a test model; inspect before signing.",
            )
            for k in SIGNAL_KINDS
        ]


def all_notes(signals: list[Signal]) -> list[str]:
    return [s.note or "" for s in signals]


def test_null_screener_is_insufficient_for_every_kind() -> None:
    result = ScreeningPipeline(NullScreener()).run(photo(), upload_id="upload-1")
    assert result.quality.quality is EvidenceQuality.good
    assert [s.kind for s in result.signals] == list(SIGNAL_KINDS)
    for s in result.signals:
        assert s.likelihood is Likelihood.insufficient_evidence
        assert s.confidence is None
        assert s.evidence_quality is EvidenceQuality.good
        assert "No screening model" in (s.note or "")
        assert s.id == f"upload-1:{s.kind.value}"


def test_poor_photo_overrides_the_screener() -> None:
    result = ScreeningPipeline(FakeScreener()).run(photo(blur=12))
    assert result.quality.quality is EvidenceQuality.poor
    assert all(s.likelihood is Likelihood.insufficient_evidence for s in result.signals)
    assert all("too low to screen" in (s.note or "") for s in result.signals)
    assert all("blurred" in (s.note or "") for s in result.signals)


def test_good_photo_reaches_the_screener() -> None:
    out = io.BytesIO()
    photo().save(out, format="PNG")
    result = ScreeningPipeline(FakeScreener()).run(out.getvalue(), upload_id="u")
    mould = next(s for s in result.signals if s.kind is SignalKind.possible_mould)
    assert mould.likelihood is Likelihood.possible


def test_pipeline_rejects_incomplete_or_mislabelled_screener_output() -> None:
    class Partial(FakeScreener):
        def screen(self, image, *, quality, upload_id):  # type: ignore[no-untyped-def]
            return super().screen(image, quality=quality, upload_id=upload_id)[:1]

    class WrongQuality(FakeScreener):
        def screen(self, image, *, quality, upload_id):  # type: ignore[no-untyped-def]
            fake = QualityReport(quality=EvidenceQuality.limited)
            return super().screen(image, quality=fake, upload_id=upload_id)

    with pytest.raises(ValueError, match="one signal per kind"):
        ScreeningPipeline(Partial()).run(photo())
    with pytest.raises(ValueError, match="quality gate"):
        ScreeningPipeline(WrongQuality()).run(photo())


def test_vision_screener_needs_a_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(NotConfigured, match="HAVEN_VISION_PROVIDER"):
        VisionModelScreener(None)
    assert isinstance(make_screener(Settings()), NullScreener)
    monkeypatch.setenv("HAVEN_VISION_PROVIDER", "someprovider")
    screener = make_screener(Settings())
    assert isinstance(screener, VisionModelScreener)
    with pytest.raises(NotConfigured, match="isn't implemented"):
        ScreeningPipeline(screener).run(photo())


@pytest.mark.parametrize("blur", [0, 12])
def test_no_screener_output_uses_certainty_phrasing(blur: float) -> None:
    for screener in (NullScreener(), FakeScreener()):
        result = ScreeningPipeline(screener).run(photo(blur=blur), upload_id="u")
        for note in all_notes(result.signals) + [s.source for s in result.signals]:
            assert certainty_phrases(note) == [], note


def test_certainty_phrase_checker() -> None:
    text = "This flat has damp and is wheelchair accessible."
    assert certainty_phrases(text) == ["has damp", "is wheelchair accessible"]
    assert certainty_phrases("Possible damp; inspect before signing. Not confirmed.") == []
    assert certainty_phrases("Mould DETECTED") == ["mould detected"]
    assert len(set(BANNED_CERTAINTY_PHRASES)) == len(BANNED_CERTAINTY_PHRASES)
