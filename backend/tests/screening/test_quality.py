"""Image quality gate on generated images: sharp, blurred, dark, bright, tiny."""

import io

import numpy as np
import pytest
from PIL import Image, ImageFilter

from haven.config import QualityThresholds, Settings
from haven.domain import EvidenceQuality
from haven.screening import assess_quality, laplacian_variance


def textured(size: tuple[int, int] = (1024, 768), seed: int = 1) -> Image.Image:
    """A detailed, well-exposed scene: random mid-tone blocks with hard edges."""
    rng = np.random.default_rng(seed)
    blocks = rng.integers(60, 200, size=(size[1] // 8, size[0] // 8), dtype=np.uint8)
    pixels = np.kron(blocks, np.ones((8, 8), dtype=np.uint8))
    return Image.fromarray(pixels).convert("RGB")


def test_sharp_photo_is_good() -> None:
    report = assess_quality(textured())
    assert report.quality is EvidenceQuality.good
    assert report.reasons == []
    assert report.metrics["width_px"] == 1024


def test_blurred_photo_is_poor() -> None:
    report = assess_quality(textured().filter(ImageFilter.GaussianBlur(12)))
    assert report.quality is EvidenceQuality.poor
    assert any("blurred" in r for r in report.reasons)


def test_slightly_blurred_photo_is_limited() -> None:
    sharp = assess_quality(textured()).metrics["laplacian_variance"]
    t = QualityThresholds(blur_variance_poor=1.0, blur_variance_good=sharp * 2)
    report = assess_quality(textured(), t)
    assert report.quality is EvidenceQuality.limited
    assert any("slightly blurred" in r for r in report.reasons)


def test_dark_photo_is_poor() -> None:
    dark = Image.fromarray((np.asarray(textured()) * 0.05).astype(np.uint8))
    report = assess_quality(dark)
    assert report.quality is EvidenceQuality.poor
    assert any("too dark" in r for r in report.reasons)


def test_overexposed_photo_is_flagged() -> None:
    pixels = np.asarray(textured()).copy()
    pixels[:, : pixels.shape[1] // 2] = 255  # half the frame blown out
    report = assess_quality(Image.fromarray(pixels))
    assert report.quality is EvidenceQuality.limited
    assert any("overexposed" in r for r in report.reasons)


@pytest.mark.parametrize(
    ("size", "quality"), [((160, 120), EvidenceQuality.poor), ((400, 300), EvidenceQuality.limited)]
)
def test_resolution(size: tuple[int, int], quality: EvidenceQuality) -> None:
    report = assess_quality(textured(size))
    assert report.quality is quality
    assert any("resolution" in r for r in report.reasons)


def test_tiny_image_does_not_crash() -> None:
    report = assess_quality(Image.new("RGB", (2, 2), (128, 128, 128)))
    assert report.quality is EvidenceQuality.poor
    assert laplacian_variance(np.zeros((2, 2))) == 0.0


def test_accepts_bytes_and_respects_exif_orientation() -> None:
    image = textured((800, 640))
    exif = image.getexif()
    exif[0x0112] = 6  # rotate 90°
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif.tobytes(), quality=95)
    report = assess_quality(out.getvalue())
    assert (report.metrics["width_px"], report.metrics["height_px"]) == (640, 800)


def test_blur_metric_is_scale_normalised() -> None:
    small = assess_quality(textured((800, 600))).metrics["laplacian_variance"]
    big = assess_quality(textured((800, 600)).resize((3200, 2400), Image.Resampling.NEAREST))
    # Upscaled 4x then normalised back to 1024 px: edges stay comparably sharp.
    assert big.metrics["laplacian_variance"] > small / 10


def test_thresholds_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAVEN_QUALITY__MIN_SIDE_PX_GOOD", "1000")
    settings = Settings()
    assert settings.quality.min_side_px_good == 1000
    report = assess_quality(textured(), settings.quality)
    assert report.quality is EvidenceQuality.limited
