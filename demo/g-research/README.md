# G-Research: Make the invisible visible

> **The brief:** Choose something that's hard to observe. You could build tools to collect your own data, or dig into public data. Show us what data is hidden, how we can find it, and what we can do with it.

## What we chose: what a rental listing doesn't show

A listing shows the asking rent, the number of bedrooms and a pin on a map. The things that decide whether a renter can actually afford and live in a home are mostly invisible:

| What's hidden | Why it matters | Why it's hard to see |
| --- | --- | --- |
| **The true monthly cost** | Council tax and energy can turn an affordable rent into an unaffordable home. A third of Scottish households were in fuel poverty in 2023. | Council tax charges sit in a council PDF; energy use depends on EPC band, size, property type and fuel; the price cap changes every quarter. |
| **Whether the home works for *this* person** | One step or an unreliable lift can rule a home out for a wheelchair user. | Access depends on the renter's own needs, the building and the routes around it. No listing field captures that. |
| **Condition** | Damp and mould are linked to respiratory illness and asthma (WHO, 2009). | Rarely mentioned and easy to miss in listing photos. |
| **Whether the rent is fair** | Advertised two-bed rents in Lothian rose about 46% from 2010 to 2019. | The statistics exist but sit in government spreadsheets that renters don't see. |

Haven's name says it: **Housing And Visibility** Edinburgh Network.

## 1. What data is hidden

The answers are mostly in public data, just scattered, in awkward formats and never joined to the listing:

- **City of Edinburgh Council** council tax charges by band, published only as a **PDF**.
- **Ofgem** energy price cap unit rates and standing charges for Southern Scotland, embedded in **chart widgets** on a web page.
- **Scottish Government EPC dataset**: about 40 quarterly CSVs of modelled energy demand for every certified Scottish home since 2016.
- **Scottish Government private sector rent statistics**: Lothian rents by bedroom count, 2010 to 2025.
- **Local Housing Allowance** rates for the Lothian area.
- **OpenStreetMap / NaPTAN / Public Health Scotland**: bus and tram stops, GP surgeries and other amenities.
- **openrouteservice**: real walking and **wheelchair** routes, including what share of each route has a known surface type.
- **The renter's own evidence**: photos, floor plans and documents they upload (letters, EPC certificates).

## 2. How we find it

Every source has its own ingest script that records the **source URL, retrieval date, licence and sha256** (see [docs/DATA_SOURCES.md](../../docs/DATA_SOURCES.md)):

| Hidden data | How Haven gets it out | Result |
| --- | --- | --- |
| Council tax PDF | `ingest_council_tax.py` parses the PDF tables | `data/reference/council_tax_edinburgh.yaml`, charges per band for 2025/26 and 2026/27 |
| Ofgem price cap | `ingest_energy_rates.py` reads the chart widgets' data, cross-checked against Ofgem's PDF | Unit rates and standing charges with `valid_from` and `valid_to` dates |
| EPC dataset | `fetch_epc.py` + `ingest_epc.py` aggregate Edinburgh heat demand per m² by EPC band × property type × fuel (median and IQR, n ≥ 30) | A model of energy use per m², with no addresses stored |
| Rent statistics | `ingest_rents.py` → `rent_stats` **TimescaleDB hypertable** on Tiger Cloud | Lothian rents by bedroom count, 2010 to 2025 |
| Amenities and stops | `ingest_osm.py` (Overpass, NaPTAN, PHS GP list) | A location cache for each property |
| Routes | `build_routes.py` (openrouteservice `foot-walking` and `wheelchair`) | Walking and wheelchair routes to university, Waverley, the Royal Infirmary and the nearest stop, with route completeness |
| Damp, mould, entrance steps in photos | **Google Gemini** vision, behind a local photo-quality check | A possible signal with what's visible, never a diagnosis |
| Facts in documents | OCR (Tesseract) + `pdfplumber` extraction, evaluated on synthetic documents in `ml/` | Extracted facts with their source |

We also **built our own data** where public data runs out: a synthetic property document generator (`ml/datasets/docs_synthetic/`) with an evaluation harness for per-field precision and recall, plus a planned consented Edinburgh photo set for evaluating screening.

## 3. What we can do with it

Haven joins all of this to one listing and one renter, then shows it:

- **True cost**: rent + council tax + modelled energy, against the renter's budget, every line labelled with its source and whether it's an estimate.
- **Rent context**: the asking rent next to the Lothian lower quartile, median and upper quartile, and the LHA rate.
- **Suitability checks**: transparent rules (budget fit, council tax band known, heating cost risk, step-free entrance, lift for the floor, walk to a stop, travel time, wheelchair route completeness), each with the facts behind it.
- **Photo screening**: possible damp, mould and entrance steps, as things to check at a viewing.
- **A map** that colours all 48 homes by whichever hidden factor matters to the renter.
- **A report**: what works, what may not, and what to check before signing.

## Making uncertainty visible too

Showing hidden data badly is worse than not showing it, so Haven also shows **what it doesn't know**:

- Every check returns `meets`, `concern` or **`unknown`**, and a missing council tax band is flagged instead of guessed.
- Every screening signal can be **`insufficient_evidence`**, and a blurred or dark photo never reaches the model.
- Routes openrouteservice can't compute are marked **`estimated`** (straight line × 1.3), not presented as real routes.
- Gemini's ratings carry **no confidence score**, because they aren't calibrated probabilities.

## Where to see it in the demo

| Step | What becomes visible |
| --- | --- |
| Map → "Heating" view | Homes where EPC band and size suggest high heating bills |
| Property → cost breakdown | The real monthly total, line by line, with sources |
| Property → rent context | Where the rent sits in Lothian rent statistics (2010 to 2025) |
| Map → "Step-free" / "Transport" views | Barriers specific to the renter's profile |
| Screening page | Possible mould in a photo, with what to check at a viewing |
| Report | Everything above, with "unknown" items listed as questions to ask |
