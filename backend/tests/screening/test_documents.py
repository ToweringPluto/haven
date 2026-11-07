"""Document extraction: PDF text, OCR fallback (skipped without Tesseract), rules, failure modes."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from haven.domain import Origin, Status
from haven.screening.documents import (
    FIELDS,
    extract_document,
    extract_fields,
    find_tesseract,
)

TESSERACT = find_tesseract()
needs_tesseract = pytest.mark.skipif(TESSERACT is None, reason="Tesseract OCR isn't installed")

TENANCY = [
    "Private Residential Tenancy (illustrative layout)",
    "Let property: Flat 2, 10 Example Street, Edinburgh",
    "Rent payable: £1,375 pcm",
    "A tenancy deposit of £1,300.00 is payable",
    "Your property is in council tax band C.",
]


def pdf(lines: list[str]) -> bytes:
    out = io.BytesIO()
    page = canvas.Canvas(out, pagesize=A4, invariant=1)
    y = A4[1] - 72
    for line in lines:
        page.drawString(72, y, line)
        y -= 18
    page.save()
    return out.getvalue()


def scan(lines: list[str]) -> bytes:
    try:
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype("arial.ttf", 32)
    except OSError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 32)
        except OSError:
            font = ImageFont.load_default(size=32)
    image = Image.new("L", (1400, 120 + 56 * len(lines)), 255)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((60, 60 + 56 * i), line, fill=0, font=font)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def values(result) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {f.name: f.evidence.value for f in result.facts}


def test_pdf_text_layer() -> None:
    result = extract_document(pdf(TENANCY), filename="lease.pdf", content_type="application/pdf")
    assert result.text_source == "pdf_text"
    assert values(result) == {
        "epc_rating": None,
        "council_tax_band": "C",
        "rent_pcm_gbp": 1375.0,
        "deposit_gbp": 1300.0,
    }
    rent = next(f for f in result.facts if f.name == "rent_pcm_gbp").evidence
    assert rent.origin is Origin.user and rent.source == "lease.pdf"
    assert rent.status is Status.known
    epc = next(f for f in result.facts if f.name == "epc_rating").evidence
    assert epc.status is Status.insufficient and epc.note == "Not found in the document."


@pytest.mark.parametrize(
    ("text", "field", "value"),
    [
        ("Current energy efficiency rating: D (62)", "epc_rating", "D"),
        ("Energy rating: B", "epc_rating", "B"),
        ("EPC band F", "epc_rating", "F"),
        ("Council Tax Band: H", "council_tax_band", "H"),
        ("Band A", "council_tax_band", "A"),
        ("Rent: £950 per calendar month", "rent_pcm_gbp", 950.0),
        ("The monthly rent is £2,100.00", "rent_pcm_gbp", 2100.0),
        ("Deposit £1,050", "deposit_gbp", 1050.0),
        ("Rent payable: GBP 800 pcm", "rent_pcm_gbp", 800.0),
    ],
)
def test_phrasings(text: str, field: str, value: object) -> None:
    assert extract_fields(text)[field][0] == value


def test_absent_and_ambiguous_values_are_never_guessed() -> None:
    fields = extract_fields("Energy rating: see full report\nRent: as agreed\nEPC band D")
    assert fields["epc_rating"][0] == "D"  # 'see' is not a band
    assert fields["rent_pcm_gbp"][0] is None
    conflict = extract_fields("Council Tax Band: B\nBand C")
    assert conflict["council_tax_band"] == (None, "Conflicting values in the document (B, C).")
    # 'EPC band D' must not be read as a council tax band.
    assert extract_fields("EPC band D")["council_tax_band"][0] is None


def test_missing_tesseract_is_insufficient_not_a_crash() -> None:
    result = extract_document(
        scan(TENANCY),
        filename="lease.png",
        content_type="image/png",
        tesseract=None,
        use_default_tesseract=False,
    )
    assert result.text_source == "none"
    assert "OCR unavailable" in (result.note or "")
    assert [f.name for f in result.facts] == list(FIELDS)
    assert all(f.evidence.status is Status.insufficient for f in result.facts)
    assert all("OCR unavailable" in (f.evidence.note or "") for f in result.facts)


def test_scanned_pdf_without_tesseract() -> None:
    out = io.BytesIO()
    page = canvas.Canvas(out, pagesize=A4, invariant=1)
    page.rect(72, 72, 200, 100)  # a page with marks but no text layer, like a scan
    page.showPage()
    page.save()
    result = extract_document(
        out.getvalue(),
        filename="scan.pdf",
        content_type="application/pdf",
        use_default_tesseract=False,
    )
    assert "OCR unavailable" in (result.note or "")
    empty = extract_document(pdf([]), filename="empty.pdf", content_type="application/pdf")
    assert empty.text_source == "none"


def test_broken_document_is_insufficient() -> None:
    result = extract_document(b"%PDF-1.4 broken", filename="x.pdf", content_type="application/pdf")
    assert result.text_source == "none" and "couldn't be read" in (result.note or "")


def test_tesseract_failure_is_insufficient(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = extract_document(
        scan(TENANCY),
        filename="lease.png",
        content_type="image/png",
        tesseract=str(tmp_path / "missing-tesseract.exe"),
    )
    assert "OCR unavailable" in (result.note or "")


@needs_tesseract
def test_ocr_reads_a_scan() -> None:
    result = extract_document(
        scan(TENANCY), filename="lease.png", content_type="image/png", tesseract=TESSERACT
    )
    assert result.text_source == "ocr"
    got = values(result)
    assert got["rent_pcm_gbp"] == 1375.0
    assert got["council_tax_band"] == "C"
    rent = next(f for f in result.facts if f.name == "rent_pcm_gbp").evidence
    assert rent.status is Status.uncertain and "OCR" in (rent.note or "")
