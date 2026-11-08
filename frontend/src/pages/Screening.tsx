import { useRef, useState, type ChangeEvent } from "react";
import { useAuth } from "../auth/AuthProvider";
import { useAuthFetch } from "../auth/authFetch";
import { sampleUrl } from "../auth/config";
import { BackLink } from "../components/BackLink";
import { useNavigation } from "../state/navigation";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { SampleLabel } from "../components/SampleLabel";
import { Status } from "../components/Status";
import { useEnumLabel } from "../api/enums";
import {
  ACCEPTED_IMAGE_TYPES,
  MAX_IMAGE_BYTES,
  likelihoodStatus,
  type PhotoScreen,
} from "../data/screening";

type ScreenState =
  | { phase: "idle"; notice?: string }
  | { phase: "loading" }
  | { phase: "done"; result: PhotoScreen; isSample: boolean; notice?: string };

async function loadSample(): Promise<PhotoScreen | null> {
  try {
    const res = await fetch(sampleUrl("photo-screen.json"));
    return res.ok ? ((await res.json()) as PhotoScreen) : null;
  } catch {
    return null;
  }
}

function validateImage(file: File): string | null {
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) return "Please choose a JPG, PNG or WebP image.";
  if (file.size > MAX_IMAGE_BYTES) return "That image is over 5 MB. Please choose a smaller one.";
  return null;
}

export default function Screening() {
  const { isAuthenticated, isConfigured, isLoading, login } = useAuth();
  const label = useEnumLabel();
  const authFetch = useAuthFetch();
  const fileInput = useRef<HTMLInputElement>(null);
  // Set when opened from a home (`#/screening/<property id>`), so "back" returns to it.
  const { param: fromPropertyId } = useNavigation();
  const [state, setState] = useState<ScreenState>({ phase: "idle" });

  const showSample = async (notice?: string) => {
    setState({ phase: "loading" });
    const sample = await loadSample();
    setState(
      sample
        ? { phase: "done", result: sample, isSample: true, notice }
        : { phase: "idle", notice: "The sample result couldn’t be loaded. Please try again." },
    );
  };

  const screenPhoto = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow re-selecting the same file
    if (!file) return;

    const problem = validateImage(file);
    if (problem) return setState({ phase: "idle", notice: problem });

    setState({ phase: "loading" });
    // Raw image body (not multipart) so the server can keep it in memory and never store it.
    const result = await authFetch<PhotoScreen>("/v1/photo-screen", {
      method: "POST",
      headers: { "Content-Type": file.type },
      body: file,
    });

    if (result.status === "ok") {
      setState({ phase: "done", result: result.data, isSample: false });
    } else if (result.status === "signin") {
      setState({ phase: "idle", notice: result.message });
    } else if (result.httpStatus && result.httpStatus < 500) {
      // Something the renter can act on (too large, wrong type, rate limited): say so.
      setState({ phase: "idle", notice: result.message });
    } else {
      // 501/503/network: the service isn't available, so keep the demo working with a sample.
      await showSample(`Live screening isn’t available right now (${result.message}).`);
    }
  };

  // Every signal "insufficient_evidence" means nothing was actually assessed (no model
  // connected, or the photo was too poor), so don't present it as a completed screening.
  const signals = state.phase === "done" ? state.result.signals : [];
  const assessed =
    signals.length === 0 || signals.some((s) => s.likelihood !== "insufficient_evidence");
  const flaggedCount = signals.filter(
    (s) => s.likelihood === "possible" || s.likelihood === "likely",
  ).length;

  return (
    <main className="screen-page shell">
      {fromPropertyId ? (
        <BackLink to="property" param={fromPropertyId}>
          Back to property
        </BackLink>
      ) : (
        <BackLink to="explore">Back to homes</BackLink>
      )}
      <div className="screen-header">
        <div className="spark-large">
          <Icon name="spark" size={30} />
        </div>
        <span className="section-kicker">AI property screening</span>
        <h1>Spot questions worth asking</h1>
        <p>
          Add a photo from the listing or your viewing. Haven will look for visible details that
          could affect suitability.
        </p>
      </div>

      {state.phase !== "done" ? (
        <div className="upload-card" aria-busy={state.phase === "loading"}>
          <div className="upload-icon">
            <Icon name="upload" size={30} />
          </div>
          {isAuthenticated ? (
            <>
              <h2>Choose a property photo</h2>
              <p>
                Your photo is sent to Google’s Gemini AI service to be checked. Haven doesn’t
                keep it.
              </p>
              <span>JPG, PNG or WebP · up to 5 MB</span>
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPTED_IMAGE_TYPES.join(",")}
                onChange={screenPhoto}
                hidden
              />
              <Button
                onClick={() => fileInput.current?.click()}
                disabled={state.phase === "loading"}
              >
                {state.phase === "loading" ? "Screening…" : "Choose photo"}
              </Button>
            </>
          ) : (
            <>
              <h2>Check a property photo</h2>
              <p>
                {isConfigured
                  ? "Sign in to upload your own photo, or explore a pre-processed example."
                  : "Explore a pre-processed example of what the check finds."}
              </p>
              <div className="upload-actions">
                {isConfigured && (
                  <Button onClick={login} disabled={isLoading}>
                    <Icon name="upload" size={18} /> Sign in to upload a photo
                  </Button>
                )}
                <Button
                  secondary={isConfigured}
                  onClick={() => showSample()}
                  disabled={state.phase === "loading"}
                >
                  {state.phase === "loading" ? "Loading…" : "View sample result"}
                </Button>
              </div>
            </>
          )}
          {state.phase === "idle" && state.notice && (
            <p className="screen-notice" role="alert">
              {state.notice}
            </p>
          )}
        </div>
      ) : (
        <div className="screen-results" aria-live="polite">
          {state.isSample && (
            <div className="sample-banner">
              <SampleLabel />
              <span>
                {state.notice ? `${state.notice} ` : ""}This is a pre-processed example, not an
                analysis of your photo.
              </span>
            </div>
          )}
          <div className="result-summary">
            <div>
              <Icon name="check" size={30} />
            </div>
            <span>
              <b>
                {state.isSample
                  ? "Sample screening"
                  : assessed
                    ? "Screening complete"
                    : "This photo couldn’t be checked"}
              </b>
              <small>
                Photo quality:{" "}
                {state.result.evidence_quality
                  ? label("evidence_quality", state.result.evidence_quality)
                  : "not assessed"}
                {assessed &&
                  ` · ${flaggedCount} ${flaggedCount === 1 ? "possible issue" : "possible issues"} to check`}
              </small>
            </span>
            <Button secondary onClick={() => setState({ phase: "idle" })}>
              {isAuthenticated ? "Screen another photo" : "Back"}
            </Button>
          </div>
          <h2>What we noticed</h2>
          {state.result.signals.length === 0 && (
            <p>
              Nothing stood out in this photo. That isn’t a clean bill of health: view the property
              in person.
            </p>
          )}
          {state.result.signals.map((signal) => {
            return (
              <div className="result-row" key={signal.id}>
                <Status type={likelihoodStatus(signal.likelihood)}>
                  {label("likelihood", signal.likelihood)}
                </Status>
                <div>
                  <h3>{label("signal_kind", signal.kind)}</h3>
                  {signal.note && <p>{signal.note}</p>}
                  {signal.confidence !== null && (
                    <small>Confidence: {Math.round(signal.confidence * 100)}%</small>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}


      <div className="disclaimer">
        <Icon name="info" />
        <p>
          <b>A helpful second look—not a professional inspection.</b> AI results can be incomplete
          or inaccurate. Always view the property, ask the landlord or agent, and seek a qualified
          professional where needed.
        </p>
      </div>
    </main>
  );
}
