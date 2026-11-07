"""Per-field precision/recall of Haven's document extraction on the synthetic documents set.

Runs in the **backend** environment (it imports ``haven``)::

    uv run --directory ml python datasets/docs_synthetic/generate.py --n 60 --seed 7
    uv run --directory backend python ../ml/eval/eval_docs.py \
        --data ../ml/datasets/docs_synthetic/out [--source pdf|image|both]

Scoring per field, over every document (including ones where the field is absent):

* true positive: the extractor gives a value and it equals the label;
* false positive: it gives a value that is wrong, or gives one when the label is null;
* false negative: the label has a value and the extractor gives none (or a wrong one).

Precision = TP / (TP + FP); recall = TP / (TP + FN). A ``null`` answer for an absent field
is the correct "insufficient evidence" and counts as neither.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from haven.screening.documents import extract_document, find_tesseract

LABEL_TO_FIELD = {
    "epc_rating": "epc_rating",
    "council_tax_band": "council_tax_band",
    "rent_pcm": "rent_pcm_gbp",
    "deposit": "deposit_gbp",
}
CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg"}


def _same(predicted: object, truth: object) -> bool:
    if isinstance(truth, int) and isinstance(predicted, float):
        return predicted == float(truth)
    return predicted == truth


def evaluate(data: Path, source: str) -> dict[str, dict[str, Counter[str]]]:
    tesseract = find_tesseract()
    kinds = ["pdf", "image"] if source == "both" else [source]
    scores: dict[str, dict[str, Counter[str]]] = {k: {} for k in kinds}
    labels = [json.loads(line) for line in (data / "labels.jsonl").read_text("utf-8").splitlines()]
    for record in labels:
        for kind in kinds:
            path = data / record["files"][kind]
            result = extract_document(
                path.read_bytes(),
                filename=path.name,
                content_type=CONTENT_TYPES[path.suffix],
                tesseract=tesseract,
                use_default_tesseract=False,
            )
            for label_name, field_name in LABEL_TO_FIELD.items():
                truth = record["fields"][label_name]
                predicted = result.value(field_name)
                counter = scores[kind].setdefault(label_name, Counter())
                if predicted is not None and _same(predicted, truth):
                    counter["tp"] += 1
                else:
                    if predicted is not None:
                        counter["fp"] += 1
                    if truth is not None:
                        counter["fn"] += 1
                        counter[f"miss:{record['variant']}"] += 1
    return scores


def report(scores: dict[str, dict[str, Counter[str]]]) -> str:
    lines = [
        f"{'source':6} {'field':17} {'precision':>9} {'recall':>7}  tp  fp  fn  misses by variant"
    ]
    for kind, fields in scores.items():
        for name, c in fields.items():
            tp, fp, fn = c["tp"], c["fp"], c["fn"]
            precision = tp / (tp + fp) if tp + fp else float("nan")
            recall = tp / (tp + fn) if tp + fn else float("nan")
            misses = {k[5:]: v for k, v in c.items() if k.startswith("miss:")}
            lines.append(
                f"{kind:6} {name:17} {precision:9.2f} {recall:7.2f} {tp:3} {fp:3} {fn:3}  {misses}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, required=True, help="generate.py output folder")
    parser.add_argument("--source", choices=["pdf", "image", "both"], default="both")
    args = parser.parse_args(argv)
    if not (args.data / "labels.jsonl").is_file():
        print(f"no labels.jsonl in {args.data}; run generate.py first", file=sys.stderr)
        return 1
    if args.source != "pdf" and find_tesseract() is None:
        print(
            "note: Tesseract not found, so every image field is 'OCR unavailable'", file=sys.stderr
        )
    print(report(evaluate(args.data, args.source)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
