# Contract changelog

Changes to `contracts/openapi.yaml`, the API contract between the Haven backend and the frontend team. The spec is generated from the backend's pydantic models (`poe export-openapi`); `poe contract-check` fails if the committed file is stale, invalid, or has examples that don't match their schemas.

Every change to the contract gets an entry here saying what changed and whether it is **breaking**. Breaking changes are agreed with the frontend team first. Versions follow semver on `info.version`: breaking → major (minor while in 0.x), additive → minor (patch while in 0.x).

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
