# Haven — Housing And Visibility Edinburgh Network

Rental listings show what is available. Haven helps Edinburgh renters find the evidence they need to judge whether a property is affordable, accessible, practical and worth investigating before they commit to living there.

> **Project scope:** Haven is a prototype and decision-support tool. It is not a legal, safety, accessibility or compliance certification system. Its assessments are indicative and should be checked against the property in person and with appropriate professional advice.

## Demo

[![Watch the Haven demo (5 min)](docs/media/haven-demo-poster.jpg)](docs/media/haven-demo.mp4)

**[▶ Watch the demo video](docs/media/haven-demo.mp4)** (5 min 26 s, MP4): setting up a renter profile, exploring Edinburgh homes on the map with filters from the profile, true cost and suitability checks, comparing homes side by side, and screening a listing photo for possible damp or mould with Google Gemini. Every home shown is an illustrative example, not a real listing.

How the project fits each HackTheBurgh challenge track, and how we used Auth0, the Google Gemini API and Tiger Cloud, is in [`demo/`](demo/README.md).

## The problem: important housing information is invisible

A rental listing usually shows the asking rent, number of bedrooms and a location. It rarely shows what a property will actually cost to live in, whether the building and surrounding routes work for a particular renter, or whether the available photographs and documents contain warning signs.

This makes housing decisions difficult because the information that matters most is often:

- **Hidden in the true cost:** council tax, energy and recurring costs can make an apparently affordable property unaffordable.
- **Personal and contextual:** a step, unreliable lift or inaccessible route may matter greatly to one renter and not at all to another.
- **Distributed across sources:** transport, amenities, property details and public information are not usually presented together.
- **Difficult to observe:** possible damp, mould, access barriers or missing evidence may only become apparent in photographs or documents.

Haven makes these factors more visible by bringing together structured property data, renter requirements, location data and uploaded evidence. It turns them into a transparent assessment of what appears suitable, what may be a concern and what the renter should investigate next.

## How Haven uses data for prediction and decision-making

Haven uses different methods for different kinds of decisions. The method is chosen to keep results explainable and to avoid asking a machine-learning model to make a judgement that can be calculated directly.

| Question | Evidence source | Method and result |
| --- | --- | --- |
| What will the property cost each month? | Listing or user-provided rent; council tax data; estimated energy and recurring costs | Deterministic calculations produce estimated monthly expenditure and compare it with the renter's budget |
| Can the property meet stated requirements? | Property facts, user requirements and location or transport data | Transparent rules check barriers such as steps, lift availability, route distance and transport access |
| What may be difficult to observe? | User-uploaded photos and property documents | Google Gemini screens photos for possible concerns and document processing extracts facts; both report missing evidence and uncertainty |
| What does the evidence mean for this renter? | Structured outputs, source metadata and the renter's priorities | A grounded plain-language explanation gives reasons and suggested next steps |

Machine learning is useful where the evidence is difficult to observe directly. An initial experiment could use labelled property images to classify visual signals such as possible damp or mould, or detect features such as an entrance step. Labels should be based on explicit annotation guidelines and reviewed examples; performance should be measured on held-out data using class-specific precision, recall and false-positive and false-negative analysis.

```text
Possible damp or mould: possible
Possible entrance step: likely
Evidence quality: insufficient for a reliable conclusion
```

These are mock outputs, not measured model probabilities. Haven should report a result as **“possible damp detected; inspect before signing”**, not **“this property has damp.”** A model must be able to return *insufficient evidence*, and its output should retain the source, evidence quality, calibrated confidence where available and uncertainty. An LLM may explain structured results in plain language, but it must not invent a property score or unsupported conclusion from a description.

The final recommendation supports the renter's judgement. It does not reject applicants, make decisions about people, or certify that a property is safe, accessible or compliant.

## How Haven makes the invisible visible

Haven's central question is:

> What does a renter need to know that a listing does not normally reveal, and what evidence can help reveal it?

The primary investigation is the gap between a property's advertised asking price and the evidence a renter needs to judge its real monthly cost and practical suitability. Property-condition screening and wider public-data enrichment are extensions of this investigation.

The system investigates the gap by:

1. **Collecting listing and user-provided information** such as rent, council tax band, EPC rating, floor, lift availability and entrance details.
2. **Adding attributable context** from public datasets, transport services and location data, with the source and date recorded.
3. **Combining it with the renter's context** such as budget, priorities and accessibility requirements.
4. **Gathering additional evidence** from uploaded photographs and property documents.
5. **Applying calculations, rules and scoped ML models** to expose costs, barriers, potential concerns and missing information.
6. **Presenting the evidence and uncertainty** in an actionable report rather than hiding it behind an unexplained score.

The goal is not to claim that data can reveal everything about a property. The goal is to distinguish what is known from listing or public data, what is supplied by the renter, what has been inferred by a model, what is estimated, what remains uncertain and what should be checked.

## Core capabilities

### 1. Property profile

The user selects a property or enters its details:

- Rent and council tax band
- EPC rating
- Floor and lift availability
- Entrance steps and other access information
- Available source information

### 2. True cost calculator

Haven estimates the real recurring cost of living there:

- Monthly rent
- Council tax
- Estimated energy costs
- Other relevant recurring costs

The estimated total is compared with the renter's stated budget. Estimates are labelled as estimates, not guarantees.

### 3. Personalised suitability assessment

Haven evaluates:

- Property accessibility
- Routes to transport and essential destinations
- Location and transport suitability
- Potential barriers in relation to the renter's requirements

It explains which available evidence may or may not meet this particular renter's stated requirements. The result is a set of suitability indicators, not a definitive judgement that a property is “good” or “bad.”

For example:

- A wheelchair user may prioritise step-free access and lift reliability.
- A student may prioritise rent, transport and proximity to university.
- A family may prioritise space, heating costs and nearby schools.
- Someone on a tight budget may prioritise total monthly expenditure.

### 4. AI property screening

The user can upload a photograph or a property document. Different processing tasks may flag:

- **Image analysis:** possible damp or mould, visible entrance steps or other apparent access barriers.
- **Document processing:** extracted facts, missing evidence or features that require further inspection.

These are potential signals for investigation, not diagnoses or certifications. Accessibility is particularly contextual: a photograph or generic property field cannot establish whether a home works for a specific person without that person's requirements and further verification.

## Example user journey

1. **Create a renter profile** — enter a monthly budget, transport needs, priorities and optional accessibility requirements.
2. **Choose a property** — select one of the example Edinburgh rental properties or enter property details.
3. **Calculate the true cost** — estimate monthly expenditure and compare it with the budget.
4. **Assess suitability** — evaluate the building, surrounding routes and the renter's requirements.
5. **Screen for potential issues** — upload a photograph or document and review possible concerns and missing evidence.
6. **Get a recommendation** — receive a report that explains what works, what may be unsuitable, what could be expensive and what needs checking before signing.

### Illustrative report

**Property Suitability Report**

*Illustrative output, not a certified assessment*

- Estimated monthly cost: £1,150
- Stated budget: £1,200
- Potential accessibility barrier: entrance steps
- Property concern: possible damp visible in an uploaded photograph
- Missing information: lift maintenance history

**Recommendation:** investigate the entrance and property condition before committing. The estimated cost is within the stated budget, but suitability is not yet established.

## Current and planned scope

| Area | Current concept | Planned validation or extension |
| --- | --- | --- |
| Cost calculation | Structured inputs and deterministic monthly estimates | Compare estimates with verified property bills and assumptions |
| Property and location data | Listing, user-provided and attributable public data | Record source, date, coverage and known gaps |
| Requirement checks | Rules grounded in renter-provided priorities | Test edge cases and review accessibility assumptions with users |
| Image analysis | Google Gemini rates possible damp, mould and entrance steps in photos (after a photo-quality check); ratings carry no confidence score | Build an annotated Edinburgh dataset, evaluate precision and recall, and test false-positive and false-negative rates |
| Documents | Rent, council tax band and EPC rating read from uploaded documents (text and OCR) and checked against the listing | Evaluate OCR, extraction accuracy and insufficient-evidence handling |
| Floor plans | Not included: Haven has no floor plan dataset | Add only once there is an attributable floor plan dataset for Edinburgh homes |
| Read-aloud | Reports are read aloud by Google Gemini text-to-speech (signed in, when configured) or the browser's built-in voice | Check pronunciation of Edinburgh place names and reading of figures |
| Personalised report | Sections built from the findings' own wording, each sentence citing its evidence; optional Gemini rewording is rejected if it changes facts or sounds certain | Check that generated text preserves evidence, uncertainty and source context |

## Proposed technical approach

Haven is designed as a hybrid decision-support system:

| Component | Approach | Output |
| --- | --- | --- |
| True cost | Deterministic calculations | Estimated monthly expenditure |
| Explicit requirements | Rules and structured data | Transparent checks and reasons |
| Image screening | Google Gemini vision model, after a deterministic photo-quality check | Potential visual concerns and evidence quality, as likelihood labels with no confidence score (Gemini's ratings aren't calibrated) |
| Documents | OCR, document extraction and task-specific rules | Extracted facts, missing evidence and features requiring inspection |
| Explanation | AI-generated natural-language summary grounded in structured results | Personalised report and next steps |

The important principle is **evidence before prediction**. Where a result can be calculated or checked with a clear rule, Haven should do that directly. ML is reserved for patterns that are hard to observe, and every prediction should be presented with its evidence and limitations, and with a confidence score only where that score has been calibrated.

## Status and limitations

Haven is a prototype / demonstration of this concept. Data sources, model performance, estimated costs and property evidence may be incomplete or inaccurate. Image and document analysis can miss issues or produce false positives. Users should verify important information with the landlord or agent, inspect the property, and seek professional advice where necessary.

## Data and limits

Every dataset is listed in [`data/datasets.yml`](data/datasets.yml), the registry. The API serves it at `GET /v1/data-sources` for the app's "Data and limits" page, and the table below is generated from it (`uv run --directory backend python scripts/render_registry.py`).

<!-- datasets-table:start (generated by backend/scripts/render_registry.py) -->

| Dataset | Use | Integration | Priority | As of | Licence | Caveats |
| --- | --- | --- | --- | --- | --- | --- |
| [Private Sector Rent Statistics, Lothian BRMA (2010 to 2025)](https://www.gov.scot/publications/private-sector-rent-statistics-scotland-2010-to-2025/) (`private_rents`) | Rent benchmark and trend | `hypertable` | P0 | 2025-09-30 | Crown copyright, Scottish Government. Open Government Licence v3.0. | Mostly advertised rents at tenant turnover, not the rents sitting tenants pay. Lothian covers three council areas (City of Edinburgh, East Lothian and Midlothian), not Edinburgh alone. Each year runs to the end of September. Studios and 5+ bedroom homes are not published. Context for a listing's rent, not a valuation of any property. |
| [Local Housing Allowance rates, Lothian, 2026 to 2027](https://www.gov.scot/publications/local-housing-allowance-rates/pages/2026-to-2027/) (`lha_rates`) | Housing support comparison (LHA vs rent) | `seed_table` | P0 | 2026-04-01 | Crown copyright, Scottish Government. Open Government Licence v3.0. | Rates are frozen for 2026-27 at the level set on 31 January 2024, so they sit below current market rents. Monthly figures are calculated as weekly x 52 / 12. The 30th percentile column has no unit label on the page; it is treated as weekly. Lothian covers three council areas, not Edinburgh alone. Eligibility and the amount paid depend on personal circumstances. |
| [City of Edinburgh Council tax charges 2026/27](https://www.edinburgh.gov.uk/downloads/file/39463/council-tax-charges-2026) (`council_tax`) | True monthly cost (council tax, water and waste water) | `seed_table` | P0 | 2026-04-01 | Copyright City of Edinburgh Council; site terms allow personal, non-commercial use and no open licence is stated. Confirm before redistribution. | Full charges before any discount, exemption or Council Tax Reduction (e.g. students, single-person discount). The property's band must come from the listing, the renter or the Scottish Assessors. |
| [Ofgem energy price cap, Southern Scotland (editable config)](https://www.ofgem.gov.uk/node/176588/) (`ofgem_cap`) | Energy bill estimate (unit rates and standing charges) | `seed_table` | P0 | 2026-10-01 | Crown copyright, Ofgem. Re-usable (not logos) under the Open Government Licence. | Caps on default tariffs for Direct Debit customers, not any renter's actual tariff. Valid 1 October to 31 December 2026; the cap changes every quarter. Edit data/config/ofgem_cap.yml when it does. |
| [Domestic Energy Performance Certificates, heat demand lookup (Edinburgh)](https://data.gov.scot/dataset/domestic_energy_performance_certificates___dataset_to_q1_2026) (`epc`) | Energy bill estimate (EPC band x floor area x heating fuel) | `seed_table` | P0 | 2026-09-30 | Open Government Licence v3.0 for non-address fields. Address fields are Royal Mail copyright with restricted use and are never read or stored. | Modelled (SAP/RdSAP) heat demand under standard occupancy, not metered use. Space and water heating only; lighting and appliances are not included. Only homes with an EPC lodged since October 2016. Address fields have licence limits, so Haven uses aggregates only. |
| [OpenStreetMap kerbs, inclines, surfaces and crossings (Overpass), around each property](https://overpass-api.de/api/interpreter) (`osm_routes`) | Step-free route and surface check | `cached_api` | P1 | 2026-11-07 | © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright). Attribution required wherever shown. | Route tags may be incomplete. Within 500 m of the seed properties, surface is tagged on 37-84% of ways, smoothness on 0-29% and incline on 2-16%. Counts of tags around each property, not a check of a specific route. Kerb heights and steps on the actual route still need checking in person. A missing tag means unknown, never step-free or smooth. The Geofabrik Scotland extract is the offline fallback. |
| [NaPTAN bus stops, City of Edinburgh (ATCO area 620)](https://beta-naptan.dft.gov.uk/download) (`naptan`) | Nearby bus stops | `cached_api` | P1 | 2026-11-07 | Crown copyright, Department for Transport. Open Government Licence v3.0. | Stop locations only, no timetables, frequency or step-free boarding information. Includes inactive stops (Status column); Haven uses active ones only. |
| [Building Standards Technical Handbook (Domestic) 4.2, access within buildings](https://www.gov.scot/publications/building-standards-technical-handbook-domestic-april-2026-pdf/) (`handbook_4_2`) | Access yardsticks (door widths, corridors, lifts) | `reference_json` | P1 | 2026-04-06 | Crown copyright, Scottish Government. Open Government Licence v3.0. | Guidance value for new building work, never a legal test of an existing rented home. Most Edinburgh flats were built long before this guidance and need not meet it. |
| [Repairing Standard checklist categories (Housing (Scotland) Act 2006 s.13)](https://www.legislation.gov.uk/asp/2006/1/section/13) (`repairing_standard`) | Condition checklist | `reference_json` | P1 | 2026-10-06 | Contains public sector information licensed under the Open Government Licence v3.0. | Reference only, never a legal test. Summaries are paraphrased; the statutory text governs. Only the Housing and Property Chamber can decide whether a home meets the standard. |
| [Landlord registration (sample numbers + official search link)](https://www.landlordregistrationscotland.gov.uk/search) (`landlord_register`) | Landlord registration check prompt | `sample` | P1 | 2026-11-07 | Invented sample numbers, same licence as this repository. Nothing is taken from the Scottish Landlord Register. | The register is never scraped. Numbers in Haven start SAMPLE- and are fake. Renters should check a real landlord on the official search page. |
| [Sample flats (invented), Leith, Marchmont and Gorgie](https://github.com/ToweringPluto/haven/blob/main/data/seed/sample_flats.json) (`sample_flats`) | Demo listings (access, rent, EPC and council tax bands) | `sample` | P0 | 2026-11-07 | Invented sample data, same licence as this repository. Area anchor points © OpenStreetMap contributors, ODbL 1.0. | All 20 flats are invented, with no real addresses, landlords or listings (is_sample=true). Each flat's coordinates are its area's anchor street point, not a building. |

<!-- datasets-table:end -->

**How the data reaches the app.** The app runs with no network. Each P0 dataset has a loader in `backend/haven/datasets/loaders/` that writes an idempotent seed file, `data/seed/<id>.json`, where every record carries `is_sample` (`true` only for invented data). Run the loaders with `uv run --directory backend python scripts/build_seeds.py`; add `--check` to fail on a stale seed. Rents also go into the `rent_stats` TimescaleDB hypertable on Tiger Cloud. Set `HAVEN_DATABASE_URL` (see `backend/.env.example`) and run `uv run --directory backend python scripts/load_db.py`, which applies the idempotent `data/sql/rent_stats.sql`. The app reads rents from the database when it is configured and falls back to the seed file when it isn't, so it still runs offline. Before loading a new rents release, run `scripts/inspect_rents_csv.py --download`. It checks the column names the loader expects. Kerb, incline, surface and crossing tags from OpenStreetMap are fetched once per seed property by `scripts/ingest_osm.py --enrich`. They are stored as `access_tags` in each property's `data/location_cache/` file, next to the nearby places and routes. NaPTAN bus stops for Edinburgh are fetched once by `scripts/fetch_cached.py` into `data/cache/naptan/`. Both scripts send one request at a time with a descriptive User-Agent and never refetch data that is already stored. Nothing calls Nominatim in bulk: the sample flats use street points geocoded once, offline.

**Licences and attribution.**

- Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/): Scottish Government (gov.scot: rent statistics, LHA rates, EPC non-address fields, Building Standards Technical Handbook), Ofgem (price cap) and the Department for Transport (NaPTAN). Legislation text is from legislation.gov.uk under the same licence.
- Map and path data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available under the Open Database Licence (ODbL 1.0). Attribution must be shown wherever OSM data is displayed.
- Council tax charges © City of Edinburgh Council. Its site terms allow personal, non-commercial use and state no open licence.

**Known limits.**

- **Lothian covers three council areas.** The rent statistics and LHA rates are for the Lothian Broad Rental Market Area: City of Edinburgh, East Lothian and Midlothian. They are not Edinburgh-only figures.
- **Rents are mostly advertised.** The rent statistics describe new lets at tenant turnover, not the rents sitting tenants pay.
- **EPC address fields have licence limits.** They are Royal Mail copyright with restricted use, so Haven reads only non-address fields and stores aggregates. EPC energy figures are modelled, not metered.
- **Route tags may be incomplete.** Within 500 m of the seed properties, OSM surface tags cover 37–84% of ways, smoothness up to 29% and incline only 2–16%. A missing tag means unknown, never step-free.
- **Guidance is not law.** Handbook 4.2 values are guidance values for new building work, and the repairing standard list is reference only. Neither is ever a legal test of a home.
- **Sample data is invented.** The sample flats and landlord registration numbers are fake (`is_sample: true`). No real addresses, landlords or listings are used, and the landlord register is never scraped.

## Running the frontend

The prototype UI lives in [`frontend/`](frontend/) (React 19, Vite, Tailwind CSS v4), generated from the Figma design and adapted to run standalone. It requires Node.js 22 or later.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check and production build to frontend/dist
```

The dev server proxies `/v1` to the FastAPI backend on port 8000 (`uv run --directory backend poe serve`, see [`docs/FRONTEND_INTEGRATION.md`](docs/FRONTEND_INTEGRATION.md)).

## Sign-in (Auth0)

Browsing, costs and requirement checks are public. Uploads, reports, saved homes, editing your profile, deleting your data and photo screening need a signed-in user, and fall back to clearly labelled sample results when signed out or when a service is unavailable, so the demo never depends on sign-in. Read-aloud uses Gemini's voice when signed in and configured, and the browser's own voice otherwise.

Accessibility settings (colour theme, high contrast, text size, a dyslexia-friendly or high-legibility font, wider text spacing, reduced motion, underlined links, a bold keyboard focus outline and read-aloud speed) open in a pop-up from the cog at the right of the top bar (or "Accessibility settings" in the phone menu), over whatever page you are on. They're saved in the browser, so they work signed out. Auth0 is optional: with no `VITE_AUTH0_*` variables set, the app runs in public/sample mode. Tenant setup and environment variables are in [`docs/AUTH0_SETUP.md`](docs/AUTH0_SETUP.md).
