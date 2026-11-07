"""Generate Haven's synthetic documents dataset (evaluation set for document extraction).

Three **generic** layouts, none copying an official template, logo or branding:

* ``epc``: an EPC-certificate-like summary (energy rating band A-G);
* ``tenancy``: a tenancy-agreement-like page (monthly rent, deposit, sometimes the band);
* ``council_tax``: a council-tax-letter-like notice (council tax band A-H).

Every document is rendered twice: a text PDF (reportlab) and a "scan" image (Pillow) with
one degradation: none, rotation, blur, JPEG artefacts or low contrast. Fields are sometimes
**deliberately omitted**; the ground truth then says ``null``. Each page carries a
"SYNTHETIC - NOT A REAL DOCUMENT" watermark, and all names and addresses are invented.

Output (gitignored): ``out/<doc_id>.pdf``, ``out/<doc_id>.<png|jpg>`` and ``out/labels.jsonl``
(one JSON object per document: id, doc_type, variant, files, fields).

Usage (from ``ml/``)::

    uv run python datasets/docs_synthetic/generate.py --n 60 --seed 1
    uv run python datasets/docs_synthetic/generate.py --n 12 --seed 1 --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DOC_TYPES = ("epc", "tenancy", "council_tax")
VARIANTS = ("clean", "rotated", "blurred", "jpeg", "low_contrast")
EPC_BANDS = "ABCDEFG"
TAX_BANDS = "ABCDEFGH"
FIELDS = ("epc_rating", "council_tax_band", "rent_pcm", "deposit")
WATERMARK = "SYNTHETIC - NOT A REAL DOCUMENT"
OMIT_RATE = 0.2

STREETS = ["Example Street", "Sample Road", "Placeholder Lane", "Fictional Terrace", "Demo Place"]
NAMES = ["A. Tenant", "B. Renter", "C. Occupier", "D. Resident"]
LANDLORDS = ["Example Lettings Ltd", "Sample Property Co", "Demo Homes"]

EPC_PHRASES = ["Current energy efficiency rating: {b} ({s})", "Energy rating: {b}", "EPC band {b}"]
RENT_PHRASES = [
    "Rent: £{r:,} per calendar month",
    "The monthly rent is £{r:,}.00",
    "Rent payable: £{r:,} pcm",
]
DEPOSIT_PHRASES = ["Deposit: £{d:,}", "A tenancy deposit of £{d:,}.00 is payable", "Deposit £{d:,}"]
BAND_PHRASES = ["Council Tax Band: {b}", "Your property is in council tax band {b}.", "Band {b}"]


@dataclass(frozen=True)
class Doc:
    id: str
    doc_type: str
    variant: str
    lines: list[str]
    fields: dict[str, str | int | None]


def _maybe(rng: random.Random, value: str | int) -> str | int | None:
    return None if rng.random() < OMIT_RATE else value


def _address(rng: random.Random) -> str:
    return f"Flat {rng.randint(1, 9)}, {rng.randint(1, 120)} {rng.choice(STREETS)}, Edinburgh"


def make_doc(index: int, rng: random.Random) -> Doc:
    doc_type = DOC_TYPES[index % len(DOC_TYPES)]
    variant = VARIANTS[(index // len(DOC_TYPES)) % len(VARIANTS)]
    fields: dict[str, str | int | None] = dict.fromkeys(FIELDS)
    lines = [WATERMARK, ""]
    address = _address(rng)
    if doc_type == "epc":
        band = _maybe(rng, rng.choice(EPC_BANDS))
        fields["epc_rating"] = band
        lines += ["Energy Performance Summary (illustrative layout)", f"Property: {address}", ""]
        lines.append(f"Assessment date: {rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/2025")
        if band is not None:
            score = {"A": 95, "B": 85, "C": 74, "D": 62, "E": 48, "F": 30, "G": 15}[str(band)]
            lines.append(rng.choice(EPC_PHRASES).format(b=band, s=score + rng.randint(-3, 3)))
        else:
            lines.append("Rating: see full report")
        lines += ["", "Main heating: boiler and radiators", "Recommendations: loft insulation"]
    elif doc_type == "tenancy":
        rent = _maybe(rng, rng.randrange(650, 2400, 25))
        deposit = _maybe(rng, rng.randrange(600, 2600, 50))
        band = rng.choice(TAX_BANDS) if rng.random() < 0.3 else None
        fields.update(rent_pcm=rent, deposit=deposit, council_tax_band=band)
        lines += ["Private Residential Tenancy (illustrative layout)", f"Let property: {address}"]
        lines += [f"Tenant: {rng.choice(NAMES)}", f"Landlord: {rng.choice(LANDLORDS)}", ""]
        lines.append(rng.choice(RENT_PHRASES).format(r=rent) if rent else "Rent: as agreed")
        if deposit is not None:
            lines.append(rng.choice(DEPOSIT_PHRASES).format(d=deposit))
        if band is not None:
            lines.append(rng.choice(BAND_PHRASES).format(b=band))
        lines += ["", "The tenant must report repairs promptly.", "Signed: ____________"]
    else:
        band = _maybe(rng, rng.choice(TAX_BANDS))
        fields["council_tax_band"] = band
        lines += ["Council Tax Notice (illustrative layout)", f"Address: {address}", ""]
        lines.append(rng.choice(BAND_PHRASES).format(b=band) if band else "Band: under review")
        lines += [f"Account reference: {rng.randint(10**7, 10**8 - 1)}", "", "Pay by direct debit."]
    return Doc(f"doc-{index:03d}-{doc_type}", doc_type, variant, lines, fields)


def write_pdf(doc: Doc, path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)  # invariant: reproducible bytes
    width, height = A4
    pdf.setFont("Helvetica", 11)
    y = height - 72
    for line in doc.lines:
        pdf.drawString(72, y, line)
        y -= 18
    pdf.save()


FONT_CANDIDATES = ("DejaVuSans.ttf", "arial.ttf", "LiberationSans-Regular.ttf")


def _font(size: int = 28) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, bool]:
    """A TrueType font with a £ glyph if one is installed; else Pillow's default (no £)."""
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size), True
        except OSError:
            continue
    return ImageFont.load_default(size=size), False


def render_image(doc: Doc, rng: random.Random) -> Image.Image:
    font, has_pound = _font()
    image = Image.new("L", (1240, 1754), 255)  # A4 at 150 dpi
    draw = ImageDraw.Draw(image)
    y = 120
    for line in doc.lines:
        text = line if has_pound else line.replace("£", "GBP ")  # never render tofu boxes
        draw.text((120, y), text, fill=20, font=font)
        y += 44
    if doc.variant == "rotated":
        image = image.rotate(rng.choice([-1, 1]) * rng.uniform(2, 6), expand=True, fillcolor=255)
    elif doc.variant == "blurred":
        image = image.filter(ImageFilter.GaussianBlur(rng.uniform(1.2, 2.0)))
    elif doc.variant == "low_contrast":
        image = ImageEnhance.Contrast(image).enhance(0.25)
    return image


def generate(n: int, seed: int, out: Path) -> list[dict[str, object]]:
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    labels = []
    for index in range(n):
        doc = make_doc(index, rng)
        pdf_path = out / f"{doc.id}.pdf"
        write_pdf(doc, pdf_path)
        image = render_image(doc, rng)
        if doc.variant == "jpeg":
            image_path = out / f"{doc.id}.jpg"
            image.save(image_path, format="JPEG", quality=rng.randint(12, 25))
        else:
            image_path = out / f"{doc.id}.png"
            image.save(image_path, format="PNG")
        record = asdict(doc)
        del record["lines"]
        record["files"] = {"pdf": pdf_path.name, "image": image_path.name}
        labels.append(record)
    with (out / "labels.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in labels:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return labels


def check(labels: list[dict[str, object]], out: Path) -> list[str]:
    problems = []
    seen_null = dict.fromkeys(FIELDS, False)
    for record in labels:
        files = record["files"]
        assert isinstance(files, dict)
        pdf = out / files["pdf"]
        if not pdf.read_bytes().startswith(b"%PDF-"):
            problems.append(f"{record['id']}: {pdf.name} isn't a PDF")
        with Image.open(out / files["image"]) as image:
            image.verify()
        fields = record["fields"]
        assert isinstance(fields, dict)
        if set(fields) != set(FIELDS):
            problems.append(f"{record['id']}: fields {sorted(fields)}")
        epc, band = fields["epc_rating"], fields["council_tax_band"]
        if epc is not None and epc not in EPC_BANDS:
            problems.append(f"{record['id']}: bad epc_rating {epc}")
        if band is not None and band not in TAX_BANDS:
            problems.append(f"{record['id']}: bad council_tax_band {band}")
        for money in ("rent_pcm", "deposit"):
            value = fields[money]
            if value is not None and not (isinstance(value, int) and value > 0):
                problems.append(f"{record['id']}: bad {money} {value}")
        for name in FIELDS:
            seen_null[name] = seen_null[name] or fields[name] is None
    types = {r["doc_type"] for r in labels}
    variants = {r["variant"] for r in labels}
    if len(labels) >= len(DOC_TYPES) * len(VARIANTS) and variants != set(VARIANTS):
        problems.append(f"variants missing: {set(VARIANTS) - variants}")
    if types != set(DOC_TYPES):
        problems.append(f"doc types missing: {set(DOC_TYPES) - types}")
    if not all(seen_null.values()):
        problems.append(f"no deliberately omitted value for: {[k for k, v in seen_null.items() if not v]}")
    return problems


def _digest(out: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(out.iterdir()):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--n", type=int, default=60, help="number of documents")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--check", action="store_true", help="validate (and test determinism)")
    args = parser.parse_args(argv)
    if args.n < len(DOC_TYPES):
        parser.error(f"--n must be at least {len(DOC_TYPES)}")
    labels = generate(args.n, args.seed, args.out)
    if args.check:
        problems = check(labels, args.out)
        with tempfile.TemporaryDirectory() as tmp:
            again = Path(tmp) / "out"
            generate(args.n, args.seed, again)
            if _digest(again) != _digest(args.out):
                problems.append("output isn't deterministic for the same --n/--seed")
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1
    counts = {t: sum(r["doc_type"] == t for r in labels) for t in DOC_TYPES}
    print(f"wrote {len(labels)} documents to {args.out} ({counts})" + (" - check ok" if args.check else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
