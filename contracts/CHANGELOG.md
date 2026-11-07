# Contract changelog

Changes to `contracts/openapi.yaml`, the API contract between the Haven backend and the frontend team. The spec is generated from the backend's pydantic models (`poe export-openapi`); `poe contract-check` fails if the committed file is stale, invalid, or has examples that don't match their schemas.

Every change to the contract gets an entry here saying what changed and whether it is **breaking**. Breaking changes are agreed with the frontend team first. Versions follow semver on `info.version`: breaking → major (minor while in 0.x), additive → minor (patch while in 0.x).

## 0.1.0 (2026-11-07)

First published contract. Not breaking (no earlier version).

- `/v1` endpoints: profiles (`POST`, `GET` list, `GET /{profile_id}`), properties (`GET` list, `POST`, `GET /{property_id}`, `POST /{property_id}/cost`, `POST /{property_id}/suitability`), uploads (`POST` multipart, `DELETE /{upload_id}`), `POST /assessments`, `GET /reports/{report_id}`, `GET /meta/enums`; plus `GET /healthz`.
- Every value that matters carries provenance through `Evidence` (`value`, `origin`, `source`, `as_of`, `confidence`, `status`, `note`). `value: null` always comes with `status: insufficient`.
- Errors are RFC 9457 `application/problem+json` (`ProblemDetail`; `errors` list on 422).
- Examples are the illustrative persona fixtures in `contracts/examples/` (wheelchair user, student, tight budget). They are not real listings or measured model outputs. The stub API currently serves these fixtures, and anything outside the persona pairs returns 501.
