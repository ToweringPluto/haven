import { useState } from "react";
import { BackLink } from "../components/BackLink";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { Status } from "../components/Status";
import type { StatusType } from "../types";

// Mock screening output — the real results will come from the image/document models.
const MOCK_RESULTS: { type: StatusType; title: string; text: string }[] = [
  {
    type: "warn",
    title: "Possible bathroom access constraint",
    text: "The shower appears to have a raised threshold. Ask the agent for its exact height.",
  },
  {
    type: "info",
    title: "Entrance not shown",
    text: "We couldn't verify whether the main entrance is step-free. Request an entrance photo or arrange a viewing.",
  },
  {
    type: "good",
    title: "Good natural light",
    text: "The living area appears to have a large south-facing window.",
  },
];

export default function Screening() {
  const [uploaded, setUploaded] = useState(false);

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
          Add photos, a floor plan or property documents. Haven will look for visible details that
          could affect suitability.
        </p>
      </div>

      {!uploaded ? (
        <div className="upload-card">
          <div>
            <Icon name="upload" size={30} />
          </div>
          <h2>Drop property files here</h2>
          <p>or click to browse from your device</p>
          <span>JPG, PNG or PDF · Up to 10 files</span>
          <Button onClick={() => setUploaded(true)}>Choose files</Button>
        </div>
      ) : (
        <div className="screen-results" aria-live="polite">
          <div className="result-summary">
            <div>
              <Icon name="check" size={30} />
            </div>
            <span>
              <b>Screening complete</b>
              <small>4 files reviewed · {MOCK_RESULTS.length} observations found</small>
            </span>
            <Button secondary onClick={() => setUploaded(false)}>
              Add more files
            </Button>
          </div>
          <h2>What we noticed</h2>
          {MOCK_RESULTS.map((r) => (
            <div className="result-row" key={r.title}>
              <Status type={r.type} />
              <div>
                <h3>{r.title}</h3>
                <p>{r.text}</p>
              </div>
            </div>
          ))}
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
