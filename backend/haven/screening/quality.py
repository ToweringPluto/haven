"""Image quality gate: is a photo good enough to screen at all?

Three transparent checks, each graded ``good`` / ``limited`` / ``poor`` against
:class:`haven.config.QualityThresholds`; the worst grade is the photo's
:class:`~haven.domain.EvidenceQuality`:

* **resolution**: the shorter side in pixels;
* **blur**: variance of a 3x3 Laplacian over the grayscale image (low = few sharp edges);
* **exposure**: share of pixels that are near-black or near-white (clipped).

These describe the *photo*, not the property. A ``poor`` photo means screening must answer
``insufficient_evidence``; it says nothing about whether a problem exists.
"""

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps

from haven.config import QualityThresholds
from haven.domain import EvidenceQuality

_ORDER = [EvidenceQuality.good, EvidenceQuality.limited, EvidenceQuality.poor]


@dataclass(frozen=True)
class QualityReport:
    """The gate's verdict, the reasons for anything below ``good``, and the raw metrics."""

    quality: EvidenceQuality
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


def _grade(value: float, poor_below: float, good_from: float) -> EvidenceQuality:
    if value < poor_below:
        return EvidenceQuality.poor
    if value < good_from:
        return EvidenceQuality.limited
    return EvidenceQuality.good


def laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the 4-neighbour Laplacian (numpy only); 0 for images under 3x3."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    g = gray.astype(np.float64)
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def _grayscale(image: Image.Image, max_side: int) -> np.ndarray:
    gray = ImageOps.exif_transpose(image).convert("L")
    longest = max(gray.size)
    if longest > max_side:
        scale = max_side / longest
        size = (max(1, round(gray.width * scale)), max(1, round(gray.height * scale)))
        gray = gray.resize(size, Image.Resampling.LANCZOS)
    return np.asarray(gray)


def assess_quality(
    image: Image.Image | bytes, thresholds: QualityThresholds | None = None
) -> QualityReport:
    """Grade a photo's usefulness as evidence (not the property's condition)."""
    t = QualityThresholds() if thresholds is None else thresholds
    if isinstance(image, bytes):
        with Image.open(io.BytesIO(image)) as opened:
            opened.load()
            return assess_quality(opened.copy(), t)

    width, height = ImageOps.exif_transpose(image).size
    short_side = min(width, height)
    gray = _grayscale(image, t.blur_analysis_side_px)
    blur = laplacian_variance(gray)
    pixels = gray.size or 1
    dark = float(np.count_nonzero(gray <= t.dark_level)) / pixels
    bright = float(np.count_nonzero(gray >= t.bright_level)) / pixels
    clipped = dark + bright

    reasons: list[str] = []
    grades: list[EvidenceQuality] = []

    res = _grade(short_side, t.min_side_px_poor, t.min_side_px_good)
    grades.append(res)
    if res is not EvidenceQuality.good:
        reasons.append(
            f"Low resolution: the shorter side is {short_side} px "
            f"({'under' if res is EvidenceQuality.poor else 'below'} "
            f"{t.min_side_px_poor if res is EvidenceQuality.poor else t.min_side_px_good} px)."
        )

    sharp = _grade(blur, t.blur_variance_poor, t.blur_variance_good)
    grades.append(sharp)
    if sharp is not EvidenceQuality.good:
        word = "very blurred" if sharp is EvidenceQuality.poor else "slightly blurred"
        reasons.append(f"The photo looks {word} (edge sharpness {blur:.1f}).")

    if clipped > t.clipped_share_good:
        exposure = (
            EvidenceQuality.poor if clipped > t.clipped_share_poor else EvidenceQuality.limited
        )
        problem = "too dark" if dark >= bright else "overexposed"
        reasons.append(f"The photo is {problem}: {clipped:.0%} of pixels are clipped.")
    else:
        exposure = EvidenceQuality.good
    grades.append(exposure)

    quality = max(grades, key=_ORDER.index)
    metrics = {
        "width_px": float(width),
        "height_px": float(height),
        "laplacian_variance": round(blur, 2),
        "dark_share": round(dark, 4),
        "bright_share": round(bright, 4),
    }
    return QualityReport(quality=quality, reasons=reasons, metrics=metrics)
