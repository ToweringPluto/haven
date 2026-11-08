# Auth0 in Haven

## What we used it for

Haven's core renter journey is **public**: anyone can build a profile, browse homes, see the true cost and suitability checks, and open a report without an account. We use **Auth0** only where an account is needed: features that **store personal data** or **cost money to run**.

| Needs sign-in | Why |
| --- | --- |
| **Photo screening** (`POST /v1/photo-screen`) | Each call is a paid Google Gemini request, so it needs a per-user rate limit |
| **Evidence uploads** (`/v1/uploads`) | Photos and documents are personal data and must belong to someone |
| **Saving reports** (`POST /v1/reports`, `GET /v1/reports`) | A saved report is tied to its owner |
| **Saved homes and account** (`/v1/me`, `/v1/me/saved-homes`) | The user's shortlist across devices |
| **Delete all my data** (`DELETE /v1/me`) | One request removes every profile, report, upload and saved home the user owns |
| Managing profiles (update/delete) | Only the owner can change their profile |

## How it works

```text
React app ──(Auth0 Universal Login, Authorization Code + PKCE)──► Auth0 tenant (UK region)
    │                                                               │
    │◄────────────── access token for the Haven API audience ───────┘
    │
    └──Authorization: Bearer <token>──► FastAPI
                                         └─ verifies RS256 signature against the tenant's JWKS,
                                            issuer, audience and expiry → user = { sub, email }
```

**Frontend** (`frontend/src/auth/`)
- `@auth0/auth0-react` handles sign-in, with refresh tokens so users stay signed in across reloads.
- `authFetch` attaches the access token to signed-in requests and turns a `401` into a "Sign in to use this feature" prompt.
- Configured by `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID` and `VITE_AUTH0_AUDIENCE`.

**Backend** (`backend/haven/api/auth.py`)
- Verifies tokens with **PyJWT** against the tenant's JWKS (keys cached for an hour, refetched on an unknown key ID). Only **RS256** is accepted.
- Reads `sub` (the stable user ID) and email from a namespaced claim added by a small **Auth0 Action**, because Auth0 access tokens don't carry email by default.
- Configured by `HAVEN_AUTH0_DOMAIN` and `HAVEN_AUTH0_AUDIENCE`. If they're empty, signed-in endpoints return `503` and everything else keeps working.
- Never logs the token or the full claims.

**Ownership and rate limits**
- Every saved record stores the creator's Auth0 `sub` as `owner_sub` (indexed in Tiger Cloud). Anyone else asking for it gets `404`, not `403`, so IDs can't be probed.
- Per-user sliding-window rate limits keyed on `sub`: by default **10 photo screenings per hour** (`HAVEN_PHOTO_SCREEN_RATE_LIMIT`).

Full setup guide: [docs/AUTH0_SETUP.md](../docs/AUTH0_SETUP.md).

## Impact on the project

| Without Auth0 | With Auth0 |
| --- | --- |
| Anyone could run up the Gemini bill by scripting the photo endpoint | Every paid call is tied to a user and rate limited |
| Uploads and reports would be readable by anyone with the ID | Records belong to their owner; others get `404` |
| We'd have had to build password storage, resets and session handling ourselves | We wrote **no password code**: Auth0 handles credentials, MFA options and account recovery |
| No way to offer "delete everything about me" | `DELETE /v1/me` removes all of a user's data in one request, which keeps the UK GDPR story simple |

It also shaped **how the app is designed**:

- **Public by default.** Because sign-in only gates storage and paid features, a renter can get full value from Haven without creating an account. That matters for people in a housing crisis who may be wary of handing over details.
- **The demo never breaks.** When a renter is signed out, or a signed-in service fails, the frontend shows labelled **sample results**, so a broken login or AI outage never stops the walkthrough.
- **UK data residency.** We chose Auth0's UK region for an Edinburgh user base.
- **Fast to build.** Standard OAuth 2.0 / OIDC let the frontend and backend be built in parallel against the OpenAPI contract, with token verification tested using locally signed RS256 tokens (`backend/tests/api/test_auth.py`).

## Next steps

- A production tenant with a custom domain and separate dev/prod tenants.
- Move rate limits from in-memory to Redis so they're shared across API instances.
- Managed, rotated secrets.
