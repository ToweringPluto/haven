# Auth0 setup

Haven uses Auth0 for a small set of signed-in features. Everything else works without logging
in, and the app runs fine with Auth0 not configured at all.

| Access | Features |
| --- | --- |
| **Public** (no login) | The whole renter journey: profile, properties, true cost, suitability, report. |
| **Signed in** | Photo screening (`POST /v1/photo-screen`), read-aloud (`POST /v1/read-aloud`), saved comparisons (dashboard), `GET /v1/me`. |

When a renter is signed out, or a signed-in service fails, the frontend shows pre-processed
results from `frontend/public/samples/`, labelled **Sample result** or **Sample audio**. A
broken login or AI service never breaks the demo.

How it fits together:

1. The React app (`@auth0/auth0-react`) signs the user in with Auth0 (Authorization Code + PKCE)
   and requests an **access token for the Haven API audience**.
2. `authFetch` sends that token as `Authorization: Bearer <token>` to the signed-in endpoints.
3. FastAPI verifies it (RS256, the tenant's JWKS, issuer `https://<domain>/`, the API audience)
   and reads `sub` and `email`. A missing or invalid token gets `401`, and the UI shows "Sign in
   to use this feature".

You need to create **one API** and **one Single Page Application** in Auth0, plus one small
**Action** so the access token carries the user's email.

---

## 1. Create a tenant

Sign up at <https://auth0.com> and create a tenant. Pick the **UK** region (or EU): Haven's users
are in Edinburgh, and keeping identity data in the UK keeps the UK GDPR story simple. The tenant
domain looks like `haven.uk.auth0.com`. Use separate tenants for development and production.

New tenants also start with a short onboarding wizard: choose **Manual setup**, application type
**Single-Page App**, and skip the generated quickstart code (the integration already exists).

## 2. Create the API (this defines the token audience)

**Applications → APIs → + Create API**

| Field | Value |
| --- | --- |
| Name | `Haven API` |
| Identifier | `https://api.haven.example`. This is the **audience**. It's just a unique string and doesn't need to resolve, but it **can't be changed later**. |
| JSON Web Token (JWT) Profile | `Auth0` |
| JSON Web Token Signing Algorithm | **RS256** (the backend only accepts RS256) |

Then, on the API's **Settings** tab:

- **Allow Offline Access: on.** Needed for refresh tokens, which keep users signed in across page
  reloads (see step 3).
- **Token Expiration:** `3600` (1 hour) is a sensible prototype default. Refresh tokens renew it
  silently.
- **RBAC / Add Permissions in the Access Token: leave off.** Haven has only two levels (public vs
  signed in), so a valid token is all the backend checks.

## 3. Create the Single Page Application

**Applications → Applications → + Create Application → Single Page Web Applications**, named
`Haven web`. On its **Settings** tab:

| Field | Development value | Add for production |
| --- | --- | --- |
| Allowed Callback URLs | `http://localhost:5173, http://localhost:4173` | `https://<your-site>` |
| Allowed Logout URLs | `http://localhost:5173, http://localhost:4173` | `https://<your-site>` |
| Allowed Web Origins | `http://localhost:5173, http://localhost:4173` | `https://<your-site>` |

`5173` is `npm run dev` and `4173` is `npm run preview`. The app uses
`redirect_uri = window.location.origin`, so register **bare origins**: no path and no trailing
slash, or Auth0 reports a *Callback URL mismatch*.

Further down the same page:

- **Refresh Token Rotation: on.** Set a reuse interval of about `10` seconds.
- **Refresh Token Expiration:** enable **Absolute Expiration** (for example 30 days) and
  **Inactivity Expiration** (for example 7 days).
- **Advanced Settings → Grant Types:** tick **Authorization Code** and **Refresh Token**. Untick
  **Implicit**.

Why refresh tokens: most browsers now block the third-party cookies that Auth0's older "silent
auth" iframe relies on. The frontend uses `useRefreshTokens` with `cacheLocation="localstorage"`
so users stay signed in after a reload. The trade-off is that tokens sit in `localStorage`,
where an XSS bug could read them. Keep the access token short-lived, keep rotation on, and don't
add untrusted scripts to the page. A custom domain (see the production checklist) removes the
need for `localStorage`, if you'd rather switch to `cacheLocation="memory"`.

Copy the **Domain** and **Client ID** from this page for step 6.

**Authorise the app for the API.** Newer tenants block an app from requesting tokens for an API
until you allow it. Without this, sign-in bounces straight back with *"Client … is not authorized
to access resource server …"*. Under **Applications → Applications → Haven Web → APIs**, turn on
**User Access** for **Haven API** (or authorise Haven Web under the API's **Application Access**
tab). Do this after creating the API in step 2.

## 4. Choose how people sign in

**Authentication → Database → Username-Password-Authentication** is enabled by default. Optionally
add **Authentication → Social → Google**. Then, on the app's **Connections** tab, enable the
connections you want.

The Google connection initially uses Auth0's shared development keys. They're fine for local
testing but show an Auth0 consent screen and are rate limited, so add your own Google OAuth
client before any real use.

## 5. Put the email in the access token (Action)

Auth0 **access tokens don't include `email`** by default (only ID tokens do), and `/v1/me` is
meant to return it. Add a post-login Action:

**Actions → Library → Create Action → Build from scratch**, named `Add email to access token`,
trigger **Login / Post Login**:

```js
/**
 * Adds the user's email to access tokens for the Haven API as a namespaced claim.
 * Namespace with a URL you control; it doesn't need to resolve.
 */
exports.onExecutePostLogin = async (event, api) => {
  const namespace = "https://haven.example";
  if (event.user.email) {
    api.accessToken.setCustomClaim(`${namespace}/email`, event.user.email);
  }
};
```

Click **Deploy**. Then go to **Actions → Triggers → post-login**, drag the Action into the flow
between *Start* and *Complete*, and click **Apply**.

The backend reads the claim name from `HAVEN_AUTH0_EMAIL_CLAIM`
(`https://haven.example/email` here). Without the Action, sign-in still works and `email` comes
back as `null`.

## 6. Configure the app

**Frontend:** copy `frontend/.env.example` to `frontend/.env.local` (git-ignored):

```
VITE_AUTH0_DOMAIN=haven.uk.auth0.com
VITE_AUTH0_CLIENT_ID=<Client ID from step 3>
VITE_AUTH0_AUDIENCE=https://api.haven.example
VITE_API_BASE_URL=
```

Leave `VITE_API_BASE_URL` empty locally. The Vite dev server proxies `/v1` to
`http://localhost:8000`, so no CORS setup is needed. If any of the three Auth0 values is
missing, the app runs in public/sample mode and hides the sign-in button.

**Backend:** the settings are environment variables:

| Variable | Example | Notes |
| --- | --- | --- |
| `HAVEN_AUTH0_DOMAIN` | `haven.uk.auth0.com` | Must be the same domain the frontend uses (it's checked as the token issuer). |
| `HAVEN_AUTH0_AUDIENCE` | `https://api.haven.example` | Exactly the API identifier from step 2. |
| `HAVEN_AUTH0_EMAIL_CLAIM` | `https://haven.example/email` | Claim added in step 5. |
| `HAVEN_PHOTO_SCREEN_MAX_BYTES` | `5242880` | Default 5 MB. |
| `HAVEN_PHOTO_SCREEN_RATE_LIMIT` | `10` | Per user per window. |
| `HAVEN_READ_ALOUD_MAX_CHARS` | `5000` | |
| `HAVEN_READ_ALOUD_RATE_LIMIT` | `30` | Per user per window. |
| `HAVEN_RATE_LIMIT_WINDOW_SECONDS` | `3600` | |
| `HAVEN_CORS_ORIGINS` | `https://<your-site>` | Only needed when the frontend calls the API cross-origin. |

PowerShell:

```powershell
$env:HAVEN_AUTH0_DOMAIN = "haven.uk.auth0.com"
$env:HAVEN_AUTH0_AUDIENCE = "https://api.haven.example"
$env:HAVEN_AUTH0_EMAIL_CLAIM = "https://haven.example/email"
uv run --directory backend poe serve
```

bash:

```bash
HAVEN_AUTH0_DOMAIN=haven.uk.auth0.com \
HAVEN_AUTH0_AUDIENCE=https://api.haven.example \
HAVEN_AUTH0_EMAIL_CLAIM=https://haven.example/email \
uv run --directory backend poe serve
```

Without `HAVEN_AUTH0_DOMAIN` and `HAVEN_AUTH0_AUDIENCE`, the signed-in endpoints return `503`
and every other endpoint is unaffected.

## 7. Check it works

1. Start the backend (step 6) and `npm run dev` in `frontend/`, then open
   <http://localhost:5173>.
2. Click **Sign in**, then sign up or log in. Your name appears in the nav.
3. Open **AI screening** and choose a photo. With `HAVEN_VISION_PROVIDER=gemini` and
   `HAVEN_GEMINI_API_KEY` set in `backend/.env`, you get Gemini's ratings for possible damp,
   mould and an entrance step. Without them the photo still gets a quality grade, but every
   rating says it couldn't be checked. Either way, a result proves the token was accepted. A
   token problem shows *"Sign in to use this feature"* instead.
   Read-aloud on a report works the same way: Gemini's voice with
   `HAVEN_READ_ALOUD_PROVIDER=gemini`, otherwise the browser's own voice.
4. **Check the backend directly:** on the API's **Test** tab in Auth0, copy the test access
   token, then:

   ```bash
   curl -H "Authorization: Bearer <token>" http://localhost:8000/v1/me
   ```

   You should get `{"sub": "<client-id>@clients", "email": null}`. Test tokens are
   machine-to-machine tokens, so they have no user email. A user's token, from the browser's
   network tab, returns their email once the step 5 Action is in place.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| *Callback URL mismatch* on the Auth0 page | The origin isn't in **Allowed Callback URLs**, or a path or trailing slash was added. |
| *Client … is not authorized to access resource server …* (shown in the app's sign-in banner) | The app isn't authorised for the API. See "Authorise the app for the API" in step 3. |
| *Service not found: https://api…* | `VITE_AUTH0_AUDIENCE` doesn't exactly match the API identifier. |
| Signed in, but every API call says "Sign in to use this feature" | The backend's audience or domain differs from the frontend's (issuer `https://<domain>/` must match exactly, including a custom domain if you use one). Or the token is opaque because no audience was requested. |
| *Missing Refresh Token* in the console | **Allow Offline Access** is off on the API, or the **Refresh Token** grant is unticked on the app. |
| Signed out after every reload | Refresh-token rotation isn't enabled (step 3). |
| CORS error calling the API | You set `VITE_API_BASE_URL` to another origin. Add that frontend origin to `HAVEN_CORS_ORIGINS`, or leave it empty and use the dev proxy. |
| `503` from `/v1/me` | The backend isn't configured (`HAVEN_AUTH0_*` unset) or couldn't reach the tenant's JWKS. |
| `429` | The per-user limit was reached. `Retry-After` says how long to wait. |

## Production checklist

- A separate **production tenant**, with the production origin in all three URL lists and the
  localhost entries removed.
- A **custom domain** (for example `login.haven.example`) under **Branding → Custom Domains**.
  Use the same value for `VITE_AUTH0_DOMAIN` and `HAVEN_AUTH0_DOMAIN`.
- Your own **Google OAuth keys** in place of Auth0's development keys.
- **Security → Attack Protection:** keep Brute-force Protection on. Consider Bot Detection and
  Breached Password Detection.
- **Rate limits:** they're in memory per process. Before running several workers or instances,
  move them to a shared store such as Redis.
- **Logs:** the backend never logs tokens or full claims. Keep it that way when adding logging.
