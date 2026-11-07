import type { StatusType } from "../types";

// Mirrors `PhotoScreen` / `Signal` in contracts/openapi.yaml (POST /v1/photo-screen).
// `public/samples/photo-screen.json` uses the same shape. Labels come from GET /v1/meta/enums.

export interface Signal {
  id: string;
  kind: string;
  likelihood: string;
  evidence_quality: string;
  confidence: number | null;
  upload_id: string | null;
  source: string;
  note: string | null;
}

export interface PhotoScreen {
  evidence_quality: string | null;
  signals: Signal[];
}

export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

/** Symbol/colour for a likelihood. The text label always comes with it (no colour-only meaning). */
export const likelihoodStatus = (likelihood: string): StatusType =>
  likelihood === "insufficient_evidence" ? "info" : likelihood === "unlikely" ? "good" : "warn";
