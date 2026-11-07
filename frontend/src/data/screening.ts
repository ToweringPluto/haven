import type { StatusType } from "../types";

// Mirrors `PhotoScreen` / `Signal` in contracts/openapi.yaml (POST /v1/photo-screen).
// `public/samples/photo-screen.json` uses the same shape.

export type Likelihood = "unlikely" | "possible" | "likely" | "insufficient_evidence";
export type EvidenceQuality = "good" | "limited" | "poor";

export interface Signal {
  id: string;
  kind: string;
  likelihood: Likelihood;
  evidence_quality: EvidenceQuality;
  confidence: number | null;
  upload_id: string | null;
  source: string;
  note: string | null;
}

export interface PhotoScreen {
  evidence_quality: EvidenceQuality | null;
  signals: Signal[];
}

export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

// Labels follow GET /v1/meta/enums; unknown values fall back to their raw value
// (the contract allows new enum values without notice).
const SIGNAL_LABELS: Record<string, string> = {
  possible_damp: "Possible damp",
  possible_mould: "Possible mould",
  entrance_step: "Possible entrance step",
};

const LIKELIHOOD: Record<Likelihood, { label: string; status: StatusType }> = {
  likely: { label: "Likely", status: "warn" },
  possible: { label: "Possible", status: "warn" },
  unlikely: { label: "Unlikely", status: "good" },
  insufficient_evidence: { label: "Insufficient evidence", status: "info" },
};

const QUALITY_LABELS: Record<EvidenceQuality, string> = {
  good: "Good photo quality",
  limited: "Limited photo quality",
  poor: "Poor photo quality",
};

export const signalLabel = (kind: string) => SIGNAL_LABELS[kind] ?? kind;
export const likelihoodInfo = (l: Likelihood) =>
  LIKELIHOOD[l] ?? { label: String(l), status: "info" as const };
export const qualityLabel = (q: EvidenceQuality | null) =>
  q ? QUALITY_LABELS[q] ?? q : "Photo quality not assessed";
