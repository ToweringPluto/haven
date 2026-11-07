# Frontend integration guide

This guide is for the team building the Haven frontend. The contract between us is
[`contracts/openapi.yaml`](../contracts/openapi.yaml) (OpenAPI 3.1, contract version **0.1.2**).
The spec is generated from the backend's pydantic models, so treat it as the source of truth. If
this guide disagrees with the spec, the spec wins, and please tell us.

Haven is a prototype decision-support tool. It is **not** a legal, safety, accessibility or
compliance certification system, and the UI must never present it as one (see
[UI obligations](#ui-obligations)).

## 1. Running the API locally

You can develop against either of two servers. Both serve the same contract and the same
illustrative persona examples.

### Option A: the real stub API (FastAPI)

You need [uv](https://docs.astral.sh/uv/). It downloads Python 3.12 itself. From the repo root:

```
uv run --directory backend poe serve        # http://localhost:8000, auto-reload
```

- Interactive docs: <http://localhost:8000/docs>. Raw spec: <http://localhost:8000/openapi.json>.
- Liveness: `GET /healthz` → `{"status": "ok"}`.
- **Current behaviour (contract 0.1.2):** profiles are the illustrative persona data in
  [`contracts/examples/`](../contracts/examples/) plus anything you create.
  - `GET /v1/properties` lists 8 **fictional seed properties** first (`seed-prop-*`, from
    `data/seed/properties.yaml`, each `illustrative: true` and titled "Illustrative property —
    not a real listing"), then the 3 persona properties, then anything you create. The seed
    deliberately includes edge cases: a missing council tax band and missing lift information
    (both `insufficient`), steps plus a 3rd floor with no lift, a cheap EPC F flat, and a
    step-free new build.
  - `POST /v1/properties/{property_id}/cost` runs the **real cost engine** for any property and
    any (or no) profile, using the reference data in `data/reference/` (Edinburgh council tax,
    Ofgem price cap, Edinburgh EPC heat demand, Ofgem typical electricity use). Its figures
    therefore differ from the illustrative cost examples in the spec. Lines that lack an input
    (e.g. no council tax band), or dates outside the reference periods on file, come back
    `insufficient`, never £0.
  - Suitability is real: `POST /v1/properties/{id}/suitability` runs the rules engine on any
    property × profile, using the cached location data (OpenStreetMap places, ORS walking and
    wheelchair routes) and the cost engine. The seed properties (`seed-prop-*`) have location
    data; other properties get `unknown` location findings. Findings therefore differ from the
    illustrative suitability examples in the spec (same schema). Travel times are walking or
    wheelchair only; public transport isn't modelled.
  - Assessment (reports) is still served by a *fixture backend* and only works for the
    exact persona pairs listed in [§3](#3-payload-walkthrough-wheelchair-user-persona). Any
    other combination returns **501** (`application/problem+json`) rather than invented data.
  - Uploads are stored on disk (`backend/var/uploads/`): JPEG, PNG, WebP or PDF only, checked
    from the file's content (anything else → **415**), max 15 MB (→ **413**). Images are saved
    with EXIF/GPS metadata removed (`metadata_stripped: true`); PDFs unchanged. `DELETE` removes
    the file. Screening isn't built yet: uploads come back with `signals: []` and
    `evidence_quality: null`.
  - Created profiles and properties are kept in memory and are lost on restart.
  - Set `HAVEN_BACKEND=fixtures` to serve **only** the fixtures (cost included, returning the
    illustrative examples), e.g. for demos that must match the spec examples exactly.
- Real engines will replace the fixtures endpoint by endpoint without changing the contract.

### Option B: the Prism mock server

You need Node.js (npx). From the repo root:

```
uv run --directory backend poe mock         # http://127.0.0.1:4010
uv run --directory backend poe mock --port 4011 --host 0.0.0.0
```

This runs a pinned `@stoplight/prism-cli` that serves the examples embedded in
`contracts/openapi.yaml`. It doesn't need Python state, and it validates your requests against
the spec. Useful Prism headers:

- `Prefer: example=student`: pick a named example. Example names are the persona keys
  `wheelchair_user`, `student` and `tight_budget`.
- `Prefer: code=404`: get a documented error response instead.

Prism doesn't keep state. For example, a `POST /v1/profiles` isn't visible to a later `GET`.

## 2. Endpoint per journey step

All endpoints live under `/v1`. Request and response bodies are JSON unless noted.

| # | Journey step | Endpoint | Notes |
| --- | --- | --- | --- |
| 0 | Load labels for enums | `GET /v1/meta/enums` | Every enum value with a human label. Use these labels and don't hard-code your own wording. |
| 1 | Renter describes their needs | `POST /v1/profiles` | Body `ProfileInput` (budget, priorities, access needs, destinations, other recurring costs). The server assigns `id`. |
| 1 | List or reopen profiles | `GET /v1/profiles`, `GET /v1/profiles/{profile_id}` | `GET /v1/profiles` returns `{items: [...]}`. |
| 2 | Browse properties | `GET /v1/properties` | Returns `{items: [...]}`. This wrapper exists so pagination can be added later without breaking you. |
| 2 | Add a property from a listing | `POST /v1/properties` | Body `PropertyInput`. Every fact is an `Evidence` object. Send unknown facts as `{"value": null, "status": "insufficient", ...}`; don't leave them out. |
| 2 | Property detail | `GET /v1/properties/{property_id}` | |
| 3 | True monthly cost | `POST /v1/properties/{property_id}/cost` | Body `{"profile_id": "..."}` (optional). Without a profile, `budget_comparison` is `unknown`. |
| 4 | Requirement checks | `POST /v1/properties/{property_id}/suitability` | Body `{"profile_id": "..."}`. Returns one `Finding` per applicable rule: `meets` / `concern` / `unknown`. |
| 5 | Upload evidence | `POST /v1/uploads` | **multipart/form-data**: `file`, `kind` (`photo` \| `floor_plan` \| `document`), optional `property_id`. Returns `201` with an `Upload`. |
| 5 | Delete evidence | `DELETE /v1/uploads/{upload_id}` | `204`. Removes the file and its derived signals. |
| 6 | Generate the report | `POST /v1/assessments` | Body `{"profile_id", "property_id", "upload_ids": [...]}`. Returns the full `Report`. |
| 6 | Reopen a report | `GET /v1/reports/{report_id}` | |
| – | Who is signed in | `GET /v1/me` | **Signed in.** Returns `{sub, email}`. See [§8](#8-signed-in-features-auth0). |
| – | Screen a photo | `POST /v1/photo-screen` | **Signed in.** Raw image body (`Content-Type: image/jpeg`, `image/png` or `image/webp`, max 5 MB). Never stored. Returns `PhotoScreen`. |
| – | Read text aloud | `POST /v1/read-aloud` | **Signed in.** Body `{"text": "..."}` (max 5000 characters). Returns `audio/mpeg`. |

## 3. Payload walkthrough: wheelchair user persona

All values below are **illustrative fixtures** (`"source": "illustrative fixture"`, property titles
start with "Illustrative property — not a real listing"). They aren't real listings or measured
model outputs. The full payloads are in `contracts/examples/wheelchair_user/`.

The persona pairs that the stub API currently answers:

| Persona | Profile id | Property id | Upload id | Report id |
| --- | --- | --- | --- | --- |
| Wheelchair user | `persona-wheelchair-user` | `ill-prop-leith-flat` | `ill-upload-wu-entrance` | `ill-report-wu` |
| Student | `persona-student` | `ill-prop-marchmont-flat` | `ill-upload-st-tenancy` | `ill-report-st` |
| Tight budget | `persona-tight-budget` | `ill-prop-gorgie-flat` | `ill-upload-tb-bathroom` | `ill-report-tb` |

**Profile** (`GET /v1/profiles/persona-wheelchair-user`). These are plain values supplied by the
renter. `null` means "not stated".

```json
{
  "id": "persona-wheelchair-user",
  "label": "Wheelchair user (illustrative persona)",
  "monthly_budget_gbp": 1250.0,
  "priorities": ["step_free_access", "lift_access", "transport_access"],
  "access": {"wheelchair_user": true, "step_free_entrance_required": true,
             "lift_required_above_floor": 0, "max_walk_to_stop_m": 400},
  "destinations": [{"name": "Royal Infirmary of Edinburgh", "latitude": 55.9216,
                    "longitude": -3.1347, "max_travel_minutes": 45}],
  "other_recurring_costs": []
}
```

**Property** (`GET /v1/properties/ill-prop-leith-flat`). Every fact is an `Evidence` object.
Two of them, side by side:

```json
"floor_level": {"value": 2, "origin": "listing", "source": "illustrative fixture",
                "as_of": "2026-11-01", "confidence": null, "status": "known", "note": "..."},
"has_lift":    {"value": null, "origin": "listing", "source": "illustrative fixture",
                "as_of": "2026-11-01", "confidence": null, "status": "insufficient",
                "note": "The listing does not say whether there is a lift."}
```

The `Evidence` rules are enforced by the server, so you can rely on them:
- `value: null` ⇔ `status: "insufficient"`.
- `confidence` is only ever set when `origin` is `model`, and it is in [0, 1].

**Cost** (`POST /v1/properties/ill-prop-leith-flat/cost` with
`{"profile_id": "persona-wheelchair-user"}`). Each line has a `monthly_gbp` Evidence plus an
optional `low_gbp`/`high_gbp` range. The total has a range and a budget comparison:

```json
{"kind": "energy", "label": "Estimated energy",
 "monthly_gbp": {"value": 90.0, "origin": "estimate", "status": "estimated", "...": "..."},
 "low_gbp": 70.0, "high_gbp": 115.0}
...
"total_monthly_gbp": {"value": 1180.0, "origin": "estimate", "status": "estimated", "...": "..."},
"total_low_gbp": 1160.0, "total_high_gbp": 1205.0,
"budget_monthly_gbp": 1250.0, "budget_comparison": "within"
```

Show the range ("about £1,180 a month, likely between £1,160 and £1,205"), not only the central
figure. A missing input makes the line (and the total) `insufficient`. It is never counted as £0.

**Suitability** (`POST /v1/properties/ill-prop-leith-flat/suitability`). Four findings:

| Finding id | Rule | Outcome | What it says |
| --- | --- | --- | --- |
| `wu-budget-fit` | `budget_fit` | `meets` | Estimated cost within budget |
| `wu-step-free-entrance` | `step_free_entrance` | `concern` | Possible entrance steps (listing says 3) |
| `wu-lift-required` | `lift_required_for_floor` | `unknown` | 2nd floor, lift not stated |
| `wu-walk-to-stop` | `walk_to_stop_within_limit` | `meets` | Bus stop estimated within 400 m |

Each finding carries `reason`, the `facts` it used (as Evidence) and, for `concern` and
`unknown`, a `next_step` to show the renter.

**Upload** (`POST /v1/uploads`, multipart, `kind=photo`, `property_id=ill-prop-leith-flat`). The
fixture example shows the shape that screening will return:

```json
{"id": "ill-upload-wu-entrance", "kind": "photo", "metadata_stripped": true,
 "evidence_quality": "good",
 "signals": [{"id": "wu-sig-entrance-step", "kind": "entrance_step", "likelihood": "likely",
              "evidence_quality": "good", "confidence": null,
              "note": "Illustrative output, not a measured model probability."}],
 "extracted_facts": []}
```

**Report** (`POST /v1/assessments` with both ids, or `GET /v1/reports/ill-report-wu`). The report
embeds the `profile`, `property`, `cost`, `findings` and `signals`, plus:
- `sections`: four headings ("What works", "What may be unsuitable", "What could be expensive",
  "Check before signing"). Each sentence has `cites`, a list of finding or signal ids. A section
  may have no sentences; show it as empty rather than hiding the heading.
- `disclaimer`: always present, and must always be rendered.
- `illustrative: true` on fixture reports.

## 4. UI obligations

These come from Haven's design constraints. They aren't optional styling choices. A UI that
breaks them misrepresents what the backend actually knows.

1. **Show origin and status on every value.** Every `Evidence` value must display, or make
   reachable in one interaction, its `origin` ("From the listing", "Public data", "Supplied by
   you", "Inferred by a model", "Estimate"), its `status`, its `source` and its `as_of` date.
   Estimates must be visibly labelled as estimates. Show `note` where present.
2. **`unknown` is not `concern`.** Use different labels, icons and styling for `unknown` ("Unknown:
   needs checking") and `concern` ("Possible concern"). An unknown means "we don't have the
   information", not "this is bad". The same goes for `budget_comparison: unknown` versus `over`,
   and for `status: insufficient`.
3. **Never aggregate into a score.** Don't sum, average, count up or weight findings into an
   overall score, grade, star rating, percentage match, "good/bad" badge or ranking. The contract
   deliberately has no such field, so don't derive one client-side. You may order or group findings
   by the renter's own `priorities`. `epc_rating` is the property's official EPC band, not a Haven
   score.
4. **Always render `Report.disclaimer`** verbatim, visibly on the report screen and in any
   export, share or print view. Mark illustrative data (`illustrative: true`, "illustrative
   fixture" sources) as illustrative.
5. **Show `insufficient_evidence` wording verbatim.** When a signal's `likelihood` is
   `insufficient_evidence`, or a status is `insufficient`, show the label "Insufficient evidence"
   from `GET /v1/meta/enums`. Don't hide the item, turn it into "no problem found", or replace it
   with a guess. Signals are possibilities to inspect ("Possible damp"), never diagnoses. Don't
   rephrase them into certainties such as "has damp", "accessible" or "safe". Only show a
   `confidence` when it is non-null, and never make one up.
6. **Offer an upload delete action.** Every upload the renter has made must have a visible delete
   control that calls `DELETE /v1/uploads/{upload_id}`. After a delete, drop the upload and its
   signals from the UI.
7. **No colour-only meaning.** Outcomes, likelihoods, statuses and budget comparisons must be
   readable without colour: always pair colour with a text label and/or an icon with an accessible
   name. Meet WCAG 2.2 AA contrast.
8. **Show next steps.** Show `next_step` for every `concern` and `unknown` finding. These are the
   "check before signing" actions.

## 5. Errors

All errors are RFC 9457 `application/problem+json` with the `ProblemDetail` schema (`type`,
`title`, `status`, `detail`, `instance`). Validation errors (`422`) add
`errors: [{loc, msg, type}]` so you can attach messages to form fields. `404` means an unknown id.
`501` means the endpoint can't answer this combination yet (fixture backend) and should be shown
as "not available yet", not as a failure of the property.

## 6. Versioning and the CHANGELOG

- The contract version is `info.version` in `contracts/openapi.yaml`. It follows semver: while in
  0.x, a **breaking** change bumps the minor version (0.1 → 0.2), and an **additive** change bumps
  the patch version (0.1.0 → 0.1.1).
- Every change to the contract has an entry in
  [`contracts/CHANGELOG.md`](../contracts/CHANGELOG.md) saying what changed and whether it is
  breaking.
- **Breaking changes are agreed with the frontend team before they merge.** Additive changes (new
  optional fields, new endpoints, new enum values) can arrive without notice, so tolerate unknown
  fields and render unknown enum values using their raw value as a fallback.
- `poe contract-check` (part of every backend change, and of CI) fails if the committed spec is stale, invalid, or has examples that
  don't match their schemas, so the spec you read is always the one the server implements.

## 7. CORS

CORS is off by default. To allow a browser frontend on another origin, set `HAVEN_CORS_ORIGINS`
to a comma-separated list of exact origins before starting the API:

```
HAVEN_CORS_ORIGINS="http://localhost:5173,http://localhost:3000" uv run --directory backend poe serve
```

PowerShell:

```
$env:HAVEN_CORS_ORIGINS = "http://localhost:5173"; uv run --directory backend poe serve
```

When the variable is set, all methods and headers are allowed for the listed origins.
Wildcards aren't recommended. Prism (`poe mock`) sends permissive CORS headers by default.

## 8. Signed-in features (Auth0)

The renter journey above is public and needs no login. Three endpoints need a signed-in user:
`GET /v1/me`, `POST /v1/photo-screen` and `POST /v1/read-aloud`. Send an Auth0 access token
issued for the Haven API audience:

```
Authorization: Bearer <access token>
```

- **Server configuration:** `HAVEN_AUTH0_DOMAIN` (e.g. `haven.eu.auth0.com`) and
  `HAVEN_AUTH0_AUDIENCE` (the Auth0 API identifier). Optional: `HAVEN_AUTH0_EMAIL_CLAIM` (the
  namespaced claim an Auth0 Action adds; access tokens don't carry `email` by default),
  `HAVEN_PHOTO_SCREEN_MAX_BYTES`, `HAVEN_PHOTO_SCREEN_RATE_LIMIT`, `HAVEN_READ_ALOUD_MAX_CHARS`,
  `HAVEN_READ_ALOUD_RATE_LIMIT` and `HAVEN_RATE_LIMIT_WINDOW_SECONDS`. Step-by-step tenant setup is
  in [`docs/AUTH0_SETUP.md`](AUTH0_SETUP.md).
- Tokens are verified as RS256 against the tenant's JWKS, with issuer `https://<domain>/` and the
  configured audience. Tokens and claims are never logged.
- **`401`**: show "Sign in to use this feature" and a sign-in button. Never treat it as a crash.
  **`429`**: the per-user limit was reached. Show the `detail` text (`Retry-After` gives the
  seconds). **`501`/`503`**: the feature isn't available on this server right now. Fall back to
  the labelled sample result.
- **Sample mode:** when the renter is signed out, or the service is unavailable, the frontend
  shows pre-processed results from `frontend/public/samples/`, visibly labelled "Sample result"
  or "Sample audio". The demo must never depend on sign-in working.
- Photos are sent as the raw request body, not multipart, so the server can keep them in memory.
  Screening signals follow the same rules as upload signals (see [UI obligations](#4-ui-obligations)).
