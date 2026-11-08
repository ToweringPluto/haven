# Google Gemini API in Haven

## What we used it for

Some of what matters about a home can't be calculated from public data. It's only visible in a photo. We use the **Google Gemini API** (through the `google-genai` Python SDK) for three jobs:

1. **Photo screening (mould detection).** Gemini looks at a renter's photo and rates three signals: **possible damp**, **possible mould** and **entrance step**.
2. **Read-aloud.** A Gemini text-to-speech model reads reports aloud for renters who prefer listening, or who have low vision or find reading hard.
3. **Report wording (optional).** Gemini rewords the report's template sentences into plainer language, under strict checks.

Everything else (cost, rules, routes) stays deterministic. Gemini is only used where nothing else can do the job.

## How photo screening works

```text
photo (JPG/PNG/WebP, ≤ 5 MB, held in memory)
   │
   ▼
1. Quality gate (local, no AI)       resolution · blur (Laplacian variance) · over/under-exposure
   │   poor → every signal "insufficient_evidence"; Gemini is never called
   ▼
2. Prepare                           resize to ≤ 1536 px, re-encode as JPEG → EXIF/GPS removed
   ▼
3. Gemini                            fixed prompt + JSON schema, temperature 0
   │   per signal: likelihood (likely / possible / unlikely / insufficient_evidence)
   │               + one sentence on what is visible
   ▼
4. Guardrails                        drop diagnosis wording · missing/unknown → insufficient_evidence
   │                                 · no confidence score shown
   ▼
Signal → "Rated possible from the photo: dark patches near the window frame.
          Look for black spots around windows, ceilings and corners."
```

**Code**
- `backend/haven/gemini.py`: a thin, JSON-only client (`GoogleGemini`) behind a `JsonModel` interface. Any SDK, network, quota or malformed response becomes one `GeminiError`.
- `backend/haven/screening/gemini.py`: `GeminiScreener`, with the prompt, response schema and guardrails.
- `backend/haven/screening/screeners.py`: chooses the screener from config. With no key, `NullScreener` answers "insufficient evidence" for everything.
- `backend/haven/explain/gemini_wording.py`: the optional report rewording.
- `backend/haven/speech.py`: read-aloud with a Gemini text-to-speech model; the raw audio is wrapped as WAV so browsers play it directly.
- `backend/scripts/check_gemini.py`: `uv run poe check-gemini [photo]` checks the key and model, and can screen a real photo.

**Where it runs in the app**
- **Screening page** (`POST /v1/photo-screen`, signed in): the photo is screened and discarded, never stored.
- **Evidence uploads** (`POST /v1/uploads`): uploaded photos are screened when stored, and the signals feed into the property's report.
- **Read aloud button** on reports (`POST /v1/read-aloud`, signed in): returns WAV audio. If Gemini isn't configured or fails, the app uses the browser's built-in voice (which stays on the device), and failing that a clearly labelled sample.

**Configuration** (`backend/.env`)

```env
HAVEN_VISION_PROVIDER="gemini"
HAVEN_GEMINI_API_KEY="..."            # from https://aistudio.google.com/apikey
HAVEN_GEMINI_MODEL="gemini-3.6-flash" # optional; default gemini-3.8-flash
HAVEN_REPORT_WORDING="gemini"         # optional; default "template"
HAVEN_READ_ALOUD_PROVIDER="gemini"    # read-aloud with Gemini text-to-speech
# HAVEN_GEMINI_TTS_MODEL="gemini-3.8-flash-lite-tts"
# HAVEN_GEMINI_TTS_VOICE="Kore"
```

## The guardrails, and why

| Guardrail | Why |
| --- | --- |
| **Quality gate first** | A blurred or dark photo can't support any conclusion, so we don't ask a model to guess and don't pay for the call |
| **Structured JSON with a fixed schema, temperature 0** | Output we can validate, with no free-text rambling and as repeatable as possible |
| **"Insufficient evidence" preferred over guessing** | The prompt says so, and any missing or invalid rating becomes `insufficient_evidence`. Haven never fills in for the model |
| **No confidence score** | Gemini's ratings aren't calibrated probabilities. Showing "87%" would be false precision |
| **Certainty wording discarded** | A description like "the flat has mould" is replaced with neutral text. Haven describes what's visible, never a diagnosis |
| **Rewording rejected if it drifts** | If Gemini's rewording changes what's cited or sounds more certain than the evidence, the template sentence is kept |
| **Privacy** | Photos are resized and re-encoded (no EXIF/GPS), processed in memory and never stored by `/photo-screen`. Report rewording and read-aloud send only report text, with no photos |
| **Fails safe** | A Gemini outage means "can't tell" for uploads and a labelled sample result on the Screening page, never a crash |
| **Costs controlled** | Sign-in required, with per-user rate limits (10 photo screenings and 30 read-aloud requests per hour by default) |

## Impact on the project

- **It made mould detection possible in a hackathon.** Training our own damp and mould classifier would need a labelled, consented Edinburgh photo set we don't have yet. Gemini's vision model let us ship the feature now, behind the same `Screener` interface a trained model would use later.
- **It made a hidden risk visible.** Damp and mould are linked to respiratory illness (WHO, 2009) and rarely mentioned in listings. Now a renter can check a photo before the viewing.
- **It kept the system honest.** Building around an uncalibrated model pushed us to design the guardrails above, and they now apply to *every* screener: no fake confidence, abstain when unsure, never diagnose.
- **It's swappable.** Because everything goes through `JsonModel` and `Screener`, the tests use fakes (no network, no key), and a better or cheaper model, or our own once evaluated, drops in without touching the API or frontend.
- **Accessibility.** The same photo pass rates **entrance steps**, which feeds the step-free checks for wheelchair users.
- **Reports you can listen to.** Gemini text-to-speech gives every report a natural-sounding read-aloud, with the browser's own voice as a fallback, so the app works for renters with low vision or reading difficulties.
- **Plainer reports** (optional), without risking invented facts.

## Lessons from integration

- **Model availability changes.** During setup, the newest models (`gemini-3.8-flash`, `gemini-3.7-flash`) returned `503 high demand` / `504` errors while `gemini-3.6-flash` worked. Keeping the model in config (`HAVEN_GEMINI_MODEL`) and adding `check-gemini` turned that from a debugging session into a one-line change.
- **Use AI Studio keys.** The `google-genai` client is configured with an API key from Google AI Studio, not Vertex AI credentials.

## Honest limits and next steps

- Gemini's ratings **haven't been evaluated** against labelled Edinburgh photos. Next: a consented, anonymised evaluation set, with per-class precision and recall against the `NullScreener` baseline (tasks P3b-03, P3b-05).
- Check Google's data-use terms for the free and paid tiers before a public launch, and enable billing for real users.
- Automatic retry and fallback to a second model during demand spikes.
