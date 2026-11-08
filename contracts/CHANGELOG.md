# Contract changelog

Changes to `contracts/openapi.yaml`, the API contract between the Haven backend and the frontend team. The spec is generated from the backend's pydantic models (`poe export-openapi`); `poe contract-check` fails if the committed file is stale, invalid, or has examples that don't match their schemas.

Every change to the contract gets an entry here saying what changed and whether it is **breaking**. Breaking changes are agreed with the frontend team first. Versions follow semver on `info.version`: breaking → major (minor while in 0.x), additive → minor (patch while in 0.x).

## 0.3.0 (2026-11-08)

**Breaking** (agreed with the frontend, which is updated in the same change).

- **Removed** `floor_plan` from `UploadKind` (and from the `upload_kind` labels in `GET /v1/meta/enums`). Haven has no floor plan dataset or model, so `POST /v1/uploads` now accepts only `photo` and `document`; `kind=floor_plan` is `422`. Upload records saved under an older format are skipped when listing, not an error.
- `POST /v1/read-aloud` now returns **`audio/wav`** (16-bit mono PCM), not `audio/mpeg`. On the engine backend it speaks the text with Google Gemini text-to-speech when `HAVEN_READ_ALOUD_PROVIDER=gemini` (the text is sent to Google and not stored); `501` when no speech service is configured, `503` if it fails.
- New server settings: `HAVEN_READ_ALOUD_PROVIDER`, `HAVEN_GEMINI_TTS_MODEL` (default `gemini-3.8-flash-lite-tts`), `HAVEN_GEMINI_TTS_VOICE` (default `Kore`).

## 0.2.0 (2026-11-08)

**Breaking** (agreed with the frontend, which is updated in the same change).

- **Removed** `POST /v1/properties` and the `PropertyInput` schema: renters can't add listings. Listings come only from the seed and the persona fixtures.
- **Sign-in now required** (Auth0 bearer token; `401` without one, `503` when sign-in isn't configured on the server) for `POST /v1/uploads`, `DELETE /v1/uploads/{upload_id}` and `POST /v1/assessments`. Uploads and reports belong to the signed-in user. Someone else's upload, report or profile is `404`. The example uploads can be cited in an assessment but can no longer be deleted.
- `GET /v1/reports/{report_id}` accepts an optional token: example reports are public, a saved report is only returned to its owner.
- New, signed in: `GET /v1/uploads` (optional `?property_id=`; `UploadList`), `GET /v1/reports` (`ReportList` of `ReportSummary`, newest first), `PUT` and `DELETE /v1/profiles/{profile_id}` (your own profiles only), `GET` and `PUT /v1/me/saved-homes` (`SavedHomes`), and `DELETE /v1/me` (deletes every profile, report, upload with its file, and saved home of the user; returns `DeletedData`).
- `RenterProfile` and `ProfileInput` have a new optional field `preferred_areas` (list of neighbourhood names; empty means anywhere).
- The seed has three more fictional low-rent listings (£595–£695 a month; 11 in all) for lower-budget demos.

## 0.1.4 (2026-11-07)

Additive, not breaking.

- `CostBreakdown` has a new optional field `rent_context` (`RentContext`): the Lothian lower quartile, median and upper quartile monthly rent for the property's bedroom count (Scottish Government Private Sector Rent Statistics), the monthly Local Housing Allowance rate for that size, `rent_vs_median` and `rent_vs_lha` (`below` / `similar` / `above`; within 5% counts as similar; `null` when the rent or rate isn't known), sources, dates and `caveats` (show every one). It is `null` for studios and 5+ bedroom homes, which aren't published. New enum `RentComparison`.
- `POST /v1/assessments` builds a real report for **any** profile and property on the engine backend: cost, rule findings, a `document_conflict` concern when an uploaded document disagrees with the listing on rent, council tax band or EPC rating, the uploads' signals, and four sections ("What works", "What may be unsuitable", "What could be expensive", "Check before signing") whose sentences cite finding/signal ids. The persona pairs without uploads of their own still return the illustrative reports. The fixture backend still returns 501 for other pairs.
- `POST /v1/uploads` now screens what it stores: photos get `evidence_quality` and one signal per kind (quality gate, then the configured screener: Google Gemini or none); floor plans get `evidence_quality` only; documents (and PDFs) get `extracted_facts`. If screening is unavailable, signals are `insufficient_evidence`; the upload never fails because of it.
- `POST /v1/photo-screen` works on the engine backend (no more 501). It returns the quality grade and signals: all `insufficient_evidence` when no model is configured, and `503` if the screening service fails. The photo is sent to Google Gemini when `HAVEN_VISION_PROVIDER=gemini`; Haven still doesn't store it. Signals never carry a `confidence` (Gemini's ratings aren't calibrated).
- `GET /v1/profiles` and `POST /v1/profiles` accept an optional Auth0 bearer token (`security: [Auth0, {}]`). A profile created while signed in belongs to that user and is listed for them. Profiles created without signing in are **no longer listed** in `GET /v1/profiles`; they can still be fetched by id. An invalid token is `401`.
- Profiles, properties and reports created through the API are saved in the database when `HAVEN_DATABASE_URL` is set, so they survive restarts.
- New server settings: `HAVEN_VISION_PROVIDER=gemini`, `HAVEN_GEMINI_API_KEY`, `HAVEN_GEMINI_MODEL`, `HAVEN_GEMINI_TIMEOUT_SECONDS`, `HAVEN_REPORT_WORDING` (`template` or `gemini`).

## 0.1.3 (2026-11-07)

Additive, not breaking.

- New public endpoint `GET /v1/data-sources`: returns `DataSourceList` (`items` of `DataSource`: `id`, `name`, `url`, `licence_note`, `as_of`, `caveats`), one item per dataset in the registry `data/datasets.yml`, for a "Data and limits" page. The documented example mirrors the registry, so it changes when registry entries do; no schema change.

## 0.1.2 (2026-11-07)

Additive, not breaking. No schema changes.

- `POST /v1/uploads` now documents two more problem+json statuses: `413` (file larger than the limit, 15 MB by default) and `415` (not a JPEG, PNG, WebP or PDF, judged from the file's content rather than its name or declared type). The engine backend stores uploads on disk and strips EXIF/GPS metadata from images (`metadata_stripped: true`); PDFs are stored unchanged. Descriptions of `POST /v1/uploads` and `DELETE /v1/uploads/{upload_id}` updated accordingly.

## 0.1.1 (2026-11-07)

Additive, not breaking. Existing endpoints are unchanged and stay public.

- New signed-in endpoints, secured with an Auth0 bearer token (`securitySchemes.Auth0`, HTTP bearer):
  - `GET /v1/me`: the verified `sub` and `email` (`CurrentUser`).
  - `POST /v1/photo-screen`: one JPG/PNG/WebP image as the raw request body (max 5 MB by default), processed in memory and never stored. Returns `PhotoScreen` (`evidence_quality`, `signals`). Rate limited per user.
  - `POST /v1/read-aloud`: `ReadAloudRequest` (`text`, max 5000 characters by default), returns `audio/mpeg`. Rate limited per user.
- New problem+json statuses on those endpoints: `401` (sign in), `413` (too large), `415` (not an accepted image), `429` (rate limited, with `Retry-After`), `503` (sign-in not configured or Auth0 unreachable). The fixture backend answers photo-screen and read-aloud with `501`.

## 0.1.0 (2026-11-07)

First published contract. Not breaking (no earlier version).

- `/v1` endpoints: profiles (`POST`, `GET` list, `GET /{profile_id}`), properties (`GET` list, `POST`, `GET /{property_id}`, `POST /{property_id}/cost`, `POST /{property_id}/suitability`), uploads (`POST` multipart, `DELETE /{upload_id}`), `POST /assessments`, `GET /reports/{report_id}`, `GET /meta/enums`; plus `GET /healthz`.
- Every value that matters carries provenance through `Evidence` (`value`, `origin`, `source`, `as_of`, `confidence`, `status`, `note`). `value: null` always comes with `status: insufficient`.
- Errors are RFC 9457 `application/problem+json` (`ProblemDetail`; `errors` list on 422).
- Examples are the illustrative persona fixtures in `contracts/examples/` (wheelchair user, student, tight budget). They are not real listings or measured model outputs. The stub API currently serves these fixtures, and anything outside the persona pairs returns 501.
