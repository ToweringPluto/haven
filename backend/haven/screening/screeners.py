"""Screeners turn a photo into possible signals; the pipeline gates them on photo quality.

* :class:`Screener` is the protocol every screener implements (H-02 adds a zero-shot one).
* :class:`NullScreener` is the default: no model, so every signal is
  ``insufficient_evidence`` with a note saying so.
* :class:`haven.screening.gemini.GeminiScreener` screens with Google Gemini
  (``HAVEN_VISION_PROVIDER=gemini`` plus ``HAVEN_GEMINI_API_KEY``).
* :class:`VisionModelScreener` is the slot for any other provider name; it raises
  :class:`NotConfigured` because no other provider is implemented.
* :class:`ScreeningPipeline` runs the quality gate first: a ``poor`` photo makes every signal
  ``insufficient_evidence``, whatever the screener would say.

Signals are possibilities to inspect, never findings about the property, and never carry a
confidence unless a calibrated model produced one.
"""

import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from PIL import Image

from haven.config import QualityThresholds, Settings
from haven.domain import EvidenceQuality, Likelihood, Signal, SignalKind
from haven.screening.quality import QualityReport, assess_quality

logger = logging.getLogger(__name__)

SIGNAL_KINDS: tuple[SignalKind, ...] = tuple(SignalKind)

_WHAT_TO_CHECK = {
    SignalKind.possible_damp: "Look for damp patches, tide marks or a musty smell at a viewing.",
    SignalKind.possible_mould: "Look for black spots around windows, ceilings and corners.",
    SignalKind.entrance_step: "Ask for a photo of the entrance or check it at a viewing.",
}


class NotConfigured(RuntimeError):
    """The requested screener isn't set up on this server."""


class Screener(Protocol):
    name: str

    def screen(
        self, image: Image.Image, *, quality: QualityReport, upload_id: str | None
    ) -> list[Signal]:
        """One signal per kind in :data:`SIGNAL_KINDS`. ``quality`` is never ``poor`` here."""
        ...


def signal_id(upload_id: str | None, kind: SignalKind) -> str:
    return f"{upload_id or 'photo'}:{kind.value}"


def insufficient(
    kind: SignalKind,
    *,
    quality: EvidenceQuality,
    upload_id: str | None,
    source: str,
    why: str,
) -> Signal:
    return Signal(
        id=signal_id(upload_id, kind),
        kind=kind,
        likelihood=Likelihood.insufficient_evidence,
        evidence_quality=quality,
        confidence=None,
        upload_id=upload_id,
        source=source,
        note=f"{why} {_WHAT_TO_CHECK[kind]}",
    )


class NullScreener:
    """No model: every signal is ``insufficient_evidence``."""

    name = "Haven NullScreener (no screening model connected)"

    def screen(
        self, image: Image.Image, *, quality: QualityReport, upload_id: str | None
    ) -> list[Signal]:
        return [
            insufficient(
                kind,
                quality=quality.quality,
                upload_id=upload_id,
                source=self.name,
                why="No screening model is connected, so this photo wasn't assessed for it.",
            )
            for kind in SIGNAL_KINDS
        ]


class VisionModelScreener:
    """Adapter slot for a vision model provider (chosen later; see task H-02)."""

    def __init__(self, provider: str | None) -> None:
        if not provider:
            raise NotConfigured("No vision provider is configured (set HAVEN_VISION_PROVIDER).")
        self.provider = provider
        self.name = f"Vision model screener ({provider})"

    def screen(
        self, image: Image.Image, *, quality: QualityReport, upload_id: str | None
    ) -> list[Signal]:
        raise NotConfigured(f"The vision provider {self.provider!r} isn't implemented yet.")


def make_screener(settings: Settings | None = None) -> Screener:
    """The configured screener: :class:`NullScreener` unless a vision provider is set.

    ``gemini`` gives :class:`haven.screening.gemini.GeminiScreener` when
    ``HAVEN_GEMINI_API_KEY`` is set, and :class:`NullScreener` (with a warning) when it isn't,
    so a missing key means "can't tell", never a crash.
    """
    settings = Settings() if settings is None else settings
    provider = settings.vision_provider
    if not provider:
        return NullScreener()
    if provider.lower() == "gemini":
        from haven.gemini import make_gemini
        from haven.screening.gemini import GeminiScreener

        model = make_gemini(settings)
        if model is None:
            logger.warning("HAVEN_VISION_PROVIDER=gemini but HAVEN_GEMINI_API_KEY isn't set")
            return NullScreener()
        return GeminiScreener(model)
    return VisionModelScreener(provider)


@dataclass(frozen=True)
class ScreeningResult:
    quality: QualityReport
    signals: list[Signal] = field(default_factory=list)


class ScreeningPipeline:
    """Quality gate, then the screener (skipped for ``poor`` photos)."""

    def __init__(self, screener: Screener, thresholds: QualityThresholds | None = None) -> None:
        self.screener = screener
        self.thresholds = QualityThresholds() if thresholds is None else thresholds

    def run(self, image: Image.Image | bytes, *, upload_id: str | None = None) -> ScreeningResult:
        if isinstance(image, bytes):
            with Image.open(io.BytesIO(image)) as opened:
                opened.load()
                return self.run(opened.copy(), upload_id=upload_id)
        report = assess_quality(image, self.thresholds)
        if report.quality is EvidenceQuality.poor:
            why = "The photo quality is too low to screen: " + " ".join(report.reasons)
            signals = [
                insufficient(
                    kind,
                    quality=EvidenceQuality.poor,
                    upload_id=upload_id,
                    source=f"Haven quality gate (before {self.screener.name})",
                    why=why,
                )
                for kind in SIGNAL_KINDS
            ]
            return ScreeningResult(quality=report, signals=signals)
        signals = self.screener.screen(image, quality=report, upload_id=upload_id)
        _check_signals(signals, report)
        return ScreeningResult(quality=report, signals=signals)


def _check_signals(signals: Sequence[Signal], report: QualityReport) -> None:
    kinds = [s.kind for s in signals]
    if sorted(kinds) != sorted(SIGNAL_KINDS):
        raise ValueError(f"screener must return one signal per kind, got {kinds}")
    for s in signals:
        if s.evidence_quality is not report.quality:
            raise ValueError("screener signals must carry the quality gate's grade")
