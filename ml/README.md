# Haven ML

A separate uv project (Python 3.12) for datasets, screening baselines and the evaluation harness. It's kept apart from `backend/` so heavy ML dependencies never end up in the API image.

```
uv run --directory ml python -c "import numpy, PIL, sklearn"   # check the environment
```

Base dependencies: numpy, pillow, scikit-learn. Heavier ones (torch, open_clip, Grounding DINO and so on) get added with `uv add --directory ml <pkg>` when a task needs them.

## Planned layout

| Path | Contents | Task |
| --- | --- | --- |
| `datasets/docs_synthetic/` | Generator for synthetic property documents (output in `out/`, gitignored) | P3-04 |
| `guidelines/` | Annotation guidelines (condition, entrance) | P3b-01 |
| `labelstudio/` | Label Studio labelling configs | P3b-02 |
| `eval/` | Evaluation harness: per-class precision/recall/F1, confusion matrix, abstention rate, calibration, FP/FN lists, model cards | P3b-03 |

## Rules

- **Evidence before prediction.** A model is only used for signals that can't be calculated or checked with a rule.
- Every model must be able to return `insufficient_evidence`. Outputs are possible signals, never diagnoses.
- Evaluation uses a frozen held-out test set and class-specific precision/recall with false-positive and false-negative analysis. A model is wired into the API only if it passes the promotion check against `NullScreener` (P3b-03).
- Every dataset has a datasheet in `docs/datasets/` (template: `docs/datasets/_TEMPLATE.md`), and its sources and licences are listed in `docs/DATA_SOURCES.md`.
- Raw and collected images are never committed. Strip EXIF/GPS data and blur people, faces and number plates before storing anything.
