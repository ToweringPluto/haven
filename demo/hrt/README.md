# HRT: Best Use of Data for Predictions & Decision Making

> **The brief:** **Massive scale**: ingest large streams of data. **Diverse inputs**: combine many datasets to build predictive features. **Real-time ML**: train models that turn raw data signals into automated decisions.

HRT turns market and alternative data into signals, and signals into decisions. Haven does the same for one of the biggest financial decisions most people make: **which home to rent**. Raw public data becomes per-property signals, and those signals become a decision a renter can act on, each with its evidence and uncertainty.

## How Haven maps onto the three pillars

### Why data matters: scale

Haven's inputs are bulk public datasets reduced to reference figures it can use instantly:

| Dataset | Raw scale | What Haven keeps |
| --- | --- | --- |
| Scottish Government EPC dataset | About 40 quarterly CSVs (Q4 2016 to Q3 2026) covering every certified Scottish home | Edinburgh heat demand per m², as a median and IQR per EPC band × property type × main fuel (groups of n ≥ 30) |
| Private sector rent statistics | Lothian, every year 2010 to 2025 (16 annual releases), five bedroom categories | `rent_stats` **TimescaleDB hypertable** on Tiger Cloud |
| OpenStreetMap / NaPTAN / PHS | Every stop, GP surgery and amenity across the demo areas | A location cache for each property |
| openrouteservice | Walking and wheelchair routes for every property to four destinations | Distance, duration and route completeness |

Each ingest script is **idempotent and recorded**: same input, same output, with source URL, retrieval date and sha256. We chose **TimescaleDB** for the rent series because it's a time series: when quarterly or monthly feeds arrive, it scales without changing the schema.

### Signal creation: diverse inputs

Haven builds features for each property and renter from inputs that never usually meet:

| Input type | Examples | Feature it builds |
| --- | --- | --- |
| Listing data | Rent, bedrooms, floor, lift, entrance, EPC band, council tax band | Basis for every check |
| Public reference data | Ofgem rates, EPC energy model, council tax charges, rent statistics, LHA | Modelled energy cost, true monthly cost, rent percentile and LHA comparison |
| Geospatial data | OSM stops and amenities, openrouteservice routes | Walk to nearest stop, travel time to the renter's places, wheelchair route completeness |
| Renter profile | Budget, priorities, mobility needs, places they travel to | Their own thresholds for each rule |
| Unstructured evidence (alternative data) | Photos, floor plans and documents the renter uploads | Possible damp, mould and entrance-step signals; facts extracted from documents |

Example feature: **modelled heating cost** = floor area × EPC heat demand per m² for that band, type and fuel → kWh → priced at the current Ofgem cap for Southern Scotland. That turns a single letter on an EPC into a **£/month** figure the renter can compare.

### Execution: models into automated decisions

Haven's decision layer is a pipeline. Each layer uses the simplest method that can answer the question:

```text
raw inputs ──► features ──► cost engine (deterministic)
                        ──► rule engine (transparent checks)       ──► findings ──► report
photo ──► quality gate ──► Gemini vision model (signals) ─────────┘
```

| Layer | Method | Decision output |
| --- | --- | --- |
| **Cost engine** | Deterministic calculation with dated reference data | Estimated monthly total vs budget |
| **Rule engine** | Eight transparent rules, each personalised to the renter's profile | `meets` / `concern` / `unknown`, with facts and a next step |
| **Quality gate** | Image heuristics (resolution, Laplacian blur variance, clipping) | `good` / `limited` / `poor`; poor photos never reach the model |
| **Vision model** | Google Gemini, structured JSON output against a fixed schema, temperature 0 | `likely` / `possible` / `unlikely` / `insufficient_evidence` for damp, mould and entrance steps |
| **Explanation** | Report sections built from the findings; optional Gemini rewording, **rejected automatically** if it changes the cited facts or sounds more certain than the evidence | A plain-language report: what works, what may not, what to check |

It runs **in real time**: a photo is screened in one request (in memory, never stored), and the cost, suitability checks and report are computed on demand for any renter–property pair.

## Model discipline: how we decide a model is good enough

This is where Haven treats prediction the way a trading desk would, and doesn't trust a model just because it answers:

- **Null baseline.** `NullScreener` returns `insufficient_evidence` for everything. A screening model is only accepted into the API if it beats that baseline on a frozen held-out set (ML workspace rule, task P3b-03).
- **Class-specific metrics.** Precision, recall, false-positive and false-negative analysis per signal, not one accuracy number.
- **No fake confidence.** Gemini's ratings aren't calibrated probabilities, so Haven shows **no confidence score** until a calibrated model produces one.
- **Ability to abstain.** Every model and rule can say "insufficient evidence", and missing answers become `insufficient_evidence`, never a guess.
- **Output guardrails.** Model descriptions that use certainty wording ("has damp", "is step-free") are discarded and replaced with neutral text.
- **Measured.** The document extractor is scored per field (precision and recall) on a synthetic document set with known labels (`ml/eval/eval_docs.py`).

## Honest limits

- The 48 properties are **fictional** seed data, so predictions show how the method works, not how accurate it is on real listings.
- Gemini screening **hasn't yet been evaluated** against labelled Edinburgh photos. That's the next step (consented set, task P3b-05).
- EPC energy figures are **modelled** (SAP/RdSAP), not metered, so heating cost is an estimate and labelled as one.

## Where to see it in the demo

1. Change the renter's budget or mobility needs and watch every rule result and map view update.
2. Open a property's cost breakdown: each line shows its features and sources.
3. Upload a blurred photo (rejected by the quality gate) and then a clear one (screened by Gemini).
4. Open the report: findings turned into decisions, with "unknown" items as next steps.
