# Data sources

Every external dataset or reference figure Haven uses (or plans to use) is listed here. A reference figure that the code relies on must also live in `data/reference/*.yaml` with `source_url`, `retrieved` and `licence` (see `haven/reference/`, task P1-01).

**Retrieval status** values:

- `not retrieved`: listed and planned, nothing downloaded yet.
- `retrieved YYYY-MM-DD`: downloaded and recorded. Add the file URL, size and sha256 under "Retrieved files" below.
- `blocked`: can't be fetched automatically. The reason is in "Known gaps".

Licences marked *to confirm* haven't been checked against the publisher's terms yet. Confirm them before the data is used, and in particular before any data is redistributed or used to train models (task P3b-04).

## Inventory

| Need | Source | URL | Licence | Retrieval status | Known gaps |
| --- | --- | --- | --- | --- | --- |
| Council tax + water + waste water charges by band, 2025/26 | City of Edinburgh Council, "Council tax charges 2025" (PDF) | https://www.edinburgh.gov.uk/downloads/file/36923/council-tax-charges-2025 | Council website content; to confirm | not retrieved | Gives charges by band only. The property's band must come from the listing, the user or the Scottish Assessors. Discounts and exemptions (e.g. full-time students, single-person discount) are not modelled. |
| Council tax + water + waste water charges by band, 2026/27 | City of Edinburgh Council, "Council tax charges 2026" (PDF) | https://www.edinburgh.gov.uk/downloads/file/39463/council-tax-charges-2026 | Council website content; to confirm | not retrieved | As above. Index page: https://www.edinburgh.gov.uk/counciltaxbands |
| Council tax band of a specific property | Scottish Assessors Association | https://www.saa.gov.uk/ | to confirm | not retrieved (lookup only, no bulk use planned) | Lookups are manual. Haven takes the band from the listing or the user and marks it `insufficient` when missing. |
| Energy unit rates and standing charges (electricity, gas), South Scotland, direct debit | Ofgem, energy price cap unit rates and standing charges | https://www.ofgem.gov.uk/information-consumers/energy-advice-households/energy-price-cap-unit-rates-and-standing-charges | Open Government Licence v3.0; to confirm on page | not retrieved | Covers capped default tariffs only. A renter's actual tariff can differ. The cap changes quarterly, so the YAML holds `valid_from`/`valid_to`. |
| Energy use per m² by EPC band, property type and main fuel (Edinburgh) | Scottish Government, "Domestic Energy Performance Certificates - Dataset to Q1 2026" | https://data.gov.scot/dataset/domestic_energy_performance_certificates___dataset_to_q1_2026 | Open Government Licence v3.0; address fields are subject to Royal Mail copyright | not retrieved | EPC energy figures are modelled (SAP/RdSAP), not metered. They cover only dwellings with a current EPC. Haven uses aggregates only and never stores addresses. 7z archive; exact file URL, size and sha256 are to be recorded by P1-04. |
| Rent context (median/mean by bedroom count, Lothian BRMA) | Scottish Government, "Private Sector Rent Statistics, Scotland, 2010 to 2025" ("Private Rents Open Data" CSV) | https://www.gov.scot/publications/private-sector-rent-statistics-scotland-2010-to-2025/ | Open Government Licence v3.0; to confirm | not retrieved | Based mostly on advertised rents at tenant turnover, not on rents that sitting tenants pay. Lothian BRMA is wider than the City of Edinburgh. Annual figures, year to end September. |
| Transport stops, shops, pharmacies, GP surgeries, schools near a property | OpenStreetMap via the Overpass API | https://overpass-api.de/api/interpreter | OpenStreetMap data © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright) | not retrieved | Completeness varies by area and feature type. Kerb, step and incline tags are sparse. Attribution must be shown wherever the data is displayed. |
| GP practices (second source) | Public Health Scotland, "GP Practice Contact Details and List Sizes" | https://www.opendata.nhs.scot/dataset/gp-practice-contact-details-and-list-sizes | Open Government Licence v3.0 | not retrieved | Quarterly snapshots; column names vary between releases. Postcodes only, no coordinates (geocoding needed). Doesn't say whether a practice is accepting patients. |
| GP practices with locations (alternative) | Improvement Service, "GP Practices - Scotland" (Spatial Hub) | https://spatialdata.gov.scot/geonetwork/srv/api/records/436dfefd-3e9c-4025-a15c-844525386771 | to confirm | not retrieved | Access terms are to be confirmed. Only needed if geocoding the PHS dataset proves unreliable. |
| Walking and wheelchair routes | openrouteservice (self-hosted via Docker, or the openrouteservice.org API with a key) | https://openrouteservice.org/ | Software GPL-3.0. Routes are derived from OSM (ODbL). Hosted API terms: to confirm | blocked (needs P2-00: Docker or an API key) | Wheelchair routing depends on sparse OSM kerb, incline and surface tags, so routes carry a data-completeness measure. Fallback: straight-line × 1.3, marked `estimated`. |
| Accessibility-barrier images (entrance steps, stairs, ramps, handrails) | HIIG, "Exploiting potentials: Teaching AI Systems to See Accessibility Barriers" (Zenodo 6554286) | https://zenodo.org/records/6554286 | to confirm (P3b-04) | not retrieved | Contents, label set and geography to be checked. Probably not Edinburgh-specific, so an Edinburgh evaluation set is still needed (P3b-05). |
| Damp/mould example images | Roboflow Universe community datasets (to be selected) | https://universe.roboflow.com/ | Varies by dataset; to confirm (P3b-04) | not retrieved | Label quality and provenance vary. Use for exploration only, never as the held-out evaluation set. |
| Floor plans | CubiCasa5K | https://github.com/CubiCasa/CubiCasa5k | to confirm (P3b-04) | not retrieved | Finnish floor plans; layouts and conventions differ from Edinburgh tenements. |
| Synthetic property documents | Generated by Haven (`ml/datasets/docs_synthetic/`, task P3-04) | (generated locally) | Same as this repository | not generated | Generic layouts only, not real certificates or letters. Real-world OCR performance can be worse. |
| Edinburgh condition and entrance evaluation images | Collected by the project (`haven-condition-eval`, `haven-entrance-edinburgh`, task P3b-05) | (collected locally, with consent) | Per the consent terms; see the datasheets | not collected | Needs consent, EXIF stripping and blurring of people, faces and plates. See `docs/datasets/`. |

## Retrieved files

Record each downloaded file here: dataset, exact file URL, retrieval date, size in bytes, sha256. Raw files live in `data/raw/` (gitignored) and are never committed.

| Dataset | File URL | Retrieved | Size (bytes) | sha256 |
| --- | --- | --- | --- | --- |
| (none yet) | | | | |

## Known gaps (cross-cutting)

- **No listing feed.** Properties are seed data (fictional, "Illustrative property — not a real listing") or come from the user. Haven doesn't scrape listing sites.
- **Lift presence and reliability** aren't in any open dataset. They come from the listing or the user, otherwise they stay `unknown`.
- **Entrance steps** come from the user, the listing or (as a possible signal only) image screening. No authoritative open source exists.
- **Energy estimates** are modelled from EPC aggregates, not from the property's own bills.
