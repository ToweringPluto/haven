import { useRef, useState, type ChangeEvent } from "react";
import { useAuth } from "../auth/AuthProvider";
import { useAuthFetch } from "../auth/authFetch";
import { sampleUrl } from "../auth/config";
import { BackLink } from "../components/BackLink";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { SampleLabel } from "../components/SampleLabel";
import { SignInPrompt } from "../components/SignInPrompt";
import { Status } from "../components/Status";
import {
  ACCEPTED_IMAGE_TYPES,
  MAX_IMAGE_BYTES,
  likelihoodInfo,
  qualityLabel,
  signalLabel,
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
  const { isAuthenticated } = useAuth();
  const authFetch = useAuthFetch();
  const fileInput = useRef<HTMLInputElement>(null);
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

  return (
    <main className="screen-page shell">
      <BackLink to="property">Back to property</BackLink>
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
          <div>
            <Icon name="upload" size={30} />
          </div>
          {isAuthenticated ? (
            <>
              <h2>Choose a property photo</h2>
              <p>Photos are analysed in memory and never stored.</p>
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
              <h2>See how screening works</h2>
              <p>Explore a pre-processed example, or sign in to screen your own photos.</p>
              <Button onClick={() => showSample()} disabled={state.phase === "loading"}>
                {state.phase === "loading" ? "Loading…" : "View sample result"}
              </Button>
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
              <b>{state.isSample ? "Sample screening" : "Screening complete"}</b>
              <small>
                {qualityLabel(state.result.evidence_quality)} · {state.result.signals.length}{" "}
                {state.result.signals.length === 1 ? "possible issue" : "possible issues"} to check
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
            const likelihood = likelihoodInfo(signal.likelihood);
            return (
              <div className="result-row" key={signal.id}>
                <Status type={likelihood.status}>{likelihood.label}</Status>
                <div>
                  <h3>{signalLabel(signal.kind)}</h3>
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

      {!isAuthenticated && <SignInPrompt message="Sign in to screen your own photos" />}

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
