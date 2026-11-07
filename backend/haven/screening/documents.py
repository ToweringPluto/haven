"""Read facts (EPC rating, council tax band, rent, deposit) from renter-supplied documents.

1. **Text first**: a PDF's own text layer via pdfplumber.
2. **OCR fallback**: images, and PDFs without a text layer, go through Tesseract (the CLI,
   fed over stdin). If Tesseract isn't installed, nothing crashes: every field comes back
   ``insufficient`` with the reason "OCR unavailable".
3. **Transparent rules**: one set of regular expressions per field. A field found with two
   different values is ``insufficient`` ("conflicting values"), never a guess.

Every fact is ``Evidence(origin=user, source=<filename>)``: the renter supplied the document,
Haven only read it. Text read by OCR is marked ``uncertain`` and says to check the document.
"""

import io
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pdfplumber
from PIL import Image, ImageOps

from haven.config import Settings
from haven.domain import CitedFact, Evidence, Origin, Status

type TextSource = Literal["pdf_text", "ocr", "none"]
type Parser = Callable[[str], str | float]

OCR_TIMEOUT_S = 60
OCR_DPI = 300
MIN_TEXT_CHARS = 20  # a PDF with less text than this is treated as scanned
WINDOWS_TESSERACT = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
)

_MONEY = r"(?:£|GBP)\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?"
PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "epc_rating": [
        re.compile(r"(?i:energy\s+(?:efficiency\s+)?rating)\s*:?\s*([A-G])(?![A-Za-z])"),
        re.compile(r"(?i:epc\s+(?:band|rating))\s*:?\s*([A-G])(?![A-Za-z])"),
    ],
    "council_tax_band": [
        re.compile(r"(?i:council\s+tax\s+band)\s*:?\s*([A-H])(?![A-Za-z])"),
        re.compile(r"^(?i:band)\s*:?\s*([A-H])(?![A-Za-z])", re.MULTILINE),
    ],
    "rent_pcm_gbp": [
        re.compile(r"(?i:\brent\b)[^£\n]{0,30}" + _MONEY),
    ],
    "deposit_gbp": [
        re.compile(r"(?i:\bdeposit\b)[^£\n]{0,40}" + _MONEY),
    ],
}
FIELDS = tuple(PATTERNS)


def _money(text: str) -> float:
    return float(text.replace(",", ""))


PARSERS: dict[str, Parser] = {
    "epc_rating": str.upper,
    "council_tax_band": str.upper,
    "rent_pcm_gbp": _money,
    "deposit_gbp": _money,
}


@dataclass(frozen=True)
class DocumentExtraction:
    """What was read, how, and one cited fact per field (``insufficient`` if not found)."""

    text_source: TextSource
    facts: list[CitedFact] = field(default_factory=list)
    note: str | None = None
    text: str = ""

    def value(self, name: str) -> str | int | float | bool | None:
        fact = next(f for f in self.facts if f.name == name)
        return fact.evidence.value


def find_tesseract(settings: Settings | None = None) -> str | None:
    configured = (Settings() if settings is None else settings).tesseract_cmd
    if configured:
        return configured if Path(configured).is_file() or shutil.which(configured) else None
    found = shutil.which("tesseract")
    if found:
        return found
    return next((str(p) for p in WINDOWS_TESSERACT if p.is_file()), None)


class OcrUnavailable(RuntimeError):
    pass


def ocr_image(image: Image.Image, tesseract: str | None) -> str:
    if tesseract is None:
        raise OcrUnavailable("Tesseract isn't installed on this server")
    prepared = ImageOps.autocontrast(ImageOps.exif_transpose(image).convert("L"))
    buffer = io.BytesIO()
    prepared.save(buffer, format="PNG")
    try:
        result = subprocess.run(
            [tesseract, "stdin", "stdout"],
            input=buffer.getvalue(),
            capture_output=True,
            timeout=OCR_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OcrUnavailable(f"Tesseract failed to run: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()[:200]
        raise OcrUnavailable(f"Tesseract failed: {detail}")
    return result.stdout.decode("utf-8", "replace")


def extract_fields(text: str) -> dict[str, tuple[str | float | None, str]]:
    """``{field: (value or None, note)}`` from plain text, by the rules in :data:`PATTERNS`."""
    results: dict[str, tuple[str | float | None, str]] = {}
    for name, patterns in PATTERNS.items():
        values: list[str | float] = []
        for pattern in patterns:
            values += [PARSERS[name](m.group(1)) for m in pattern.finditer(text)]
        distinct = list(dict.fromkeys(values))
        if not distinct:
            results[name] = (None, "Not found in the document.")
        elif len(distinct) > 1:
            shown = ", ".join(str(v) for v in distinct)
            results[name] = (None, f"Conflicting values in the document ({shown}).")
        else:
            results[name] = (distinct[0], "Read from the document.")
    return results


def _facts(text: str, source_name: str, text_source: TextSource) -> list[CitedFact]:
    facts = []
    for name, (value, note) in extract_fields(text).items():
        status = Status.known
        if value is None:
            status = Status.insufficient
        elif text_source == "ocr":
            status = Status.uncertain
            note = "Read by OCR from a scan or photo; check it against the document."
        facts.append(
            CitedFact(
                name=name,
                evidence=Evidence[str | int | float | bool](
                    value=value,
                    origin=Origin.user,
                    source=source_name,
                    status=status,
                    note=note,
                ),
            )
        )
    return facts


def _all_insufficient(source_name: str, why: str) -> list[CitedFact]:
    return [
        CitedFact(
            name=name,
            evidence=Evidence[str | int | float | bool](
                value=None,
                origin=Origin.user,
                source=source_name,
                status=Status.insufficient,
                note=why,
            ),
        )
        for name in FIELDS
    ]


def _pdf_text(content: bytes) -> tuple[str, list[Image.Image]]:
    """The PDF's text layer and, for pages without text, rendered page images."""
    texts, scans = [], []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            texts.append(text)
            if len(text.strip()) < MIN_TEXT_CHARS:
                scans.append(page.to_image(resolution=OCR_DPI).original.copy())
    return "\n".join(texts), scans


def extract_document(
    content: bytes,
    *,
    filename: str,
    content_type: str,
    tesseract: str | None = None,
    use_default_tesseract: bool = True,
) -> DocumentExtraction:
    """Read the four fields from a PDF or image. Never raises for unreadable documents."""
    if tesseract is None and use_default_tesseract:
        tesseract = find_tesseract()
    try:
        if content_type == "application/pdf":
            text, scans = _pdf_text(content)
            if len(text.strip()) >= MIN_TEXT_CHARS:
                return DocumentExtraction("pdf_text", _facts(text, filename, "pdf_text"), text=text)
            images = scans
        else:
            with Image.open(io.BytesIO(content)) as opened:
                opened.load()
                images = [opened.copy()]
        if not images:
            why = "The document has no pages to read."
            return DocumentExtraction("none", _all_insufficient(filename, why), note=why)
        text = "\n".join(ocr_image(image, tesseract) for image in images)
    except OcrUnavailable as exc:
        why = f"OCR unavailable ({exc}), so this scanned document couldn't be read."
        return DocumentExtraction("none", _all_insufficient(filename, why), note=why)
    except Exception as exc:  # noqa: BLE001 - a broken upload must never crash extraction
        why = f"The document couldn't be read ({type(exc).__name__})."
        return DocumentExtraction("none", _all_insufficient(filename, why), note=why)
    return DocumentExtraction("ocr", _facts(text, filename, "ocr"), text=text)
