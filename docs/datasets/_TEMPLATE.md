# Datasheet: `<dataset-name>`

Copy this file to `docs/datasets/<dataset-name>.md` and fill in every section. Write "unknown" or "not applicable" rather than deleting a section.

- **Version / date:**
- **Maintainer:**
- **Location:** (path under `ml/datasets/` or `data/`; raw data is never committed)

## Purpose

What the dataset is for (which Haven component, which task), and what it must **not** be used for. A dataset built to evaluate a "possible signal" screener must not be presented as evidence that a property is safe, accessible or free of damp.

## Composition

- What one instance is (an image, a document page, a property record).
- Number of instances, overall and per class/label.
- Fields and labels, with types and allowed values (including `insufficient_evidence`).
- Whether it contains personal data (faces, addresses, number plates, EXIF/GPS) and how that is handled.

## Sourcing and consent

- Where each part came from (URL, collection method, date range).
- Consent: who agreed to what, and how consent can be withdrawn and the item removed.
- Pre-processing applied before storage (EXIF/GPS stripping, blurring, resizing).

## Licence

- Licence of the data, and of each upstream source if it differs.
- Attribution requirements.
- Whether redistribution and model training are allowed.

## Labelling

- Labelling guide: link to the guideline in `ml/guidelines/`.
- Who labelled the data (number of annotators, training given).
- Double-annotation rate, arbitration procedure and inter-annotator agreement (Cohen's κ) achieved against the target.

## Splits

- Train / validation / held-out test sizes and how the split was made (e.g. grouped by property so images of the same property never cross splits).
- The held-out test set is frozen. Record its creation date and never tune on it.

## Known biases and limitations

- Coverage gaps (building types, neighbourhoods, lighting, camera quality, seasons).
- Label ambiguity and classes that are hard to see in photos.
- Ways the data differs from what Haven will see in use.

## Maintenance

- Who updates it, how often, and how versions are numbered.
- How errors and takedown requests are reported and handled.
- Changelog of versions.
