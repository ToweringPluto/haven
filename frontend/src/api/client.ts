import { API_BASE_URL } from "../auth/config";
import type {
  CostBreakdown,
  EnumsResponse,
  ProfileInput,
  Property,
  RenterProfile,
  Report,
  SuitabilityAssessment,
} from "./types";

/** Result of a public API call. Never thrown: every failure is a value the UI can render. */
export type Loaded<T> =
  | { status: "ok"; data: T }
  | { status: "unavailable"; message: string } // 501: the backend can't answer this yet
  | { status: "not_found"; message: string }
  | { status: "error"; message: string };

/** RFC 9457 problem+json `detail`, or a generic message. */
async function problemDetail(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // not JSON
  }
  return `The Haven service returned an error (${res.status}).`;
}

async function request<T>(path: string, init?: RequestInit): Promise<Loaded<T>> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
    });
    if (res.ok) return { status: "ok", data: (await res.json()) as T };
    const message = await problemDetail(res);
    if (res.status === 501) return { status: "unavailable", message };
    if (res.status === 404) return { status: "not_found", message };
    return { status: "error", message };
  } catch {
    return {
      status: "error",
      message: "Couldn’t reach the Haven service. Is the backend running?",
    };
  }
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  enums: () => request<EnumsResponse>("/v1/meta/enums"),
  properties: () => request<{ items: Property[] }>("/v1/properties"),
  property: (id: string) => request<Property>(`/v1/properties/${encodeURIComponent(id)}`),
  profile: (id: string) => request<RenterProfile>(`/v1/profiles/${encodeURIComponent(id)}`),
  createProfile: (input: ProfileInput) => post<RenterProfile>("/v1/profiles", input),
  cost: (propertyId: string, profileId: string | null) =>
    post<CostBreakdown>(`/v1/properties/${encodeURIComponent(propertyId)}/cost`, {
      profile_id: profileId,
    }),
  suitability: (propertyId: string, profileId: string) =>
    post<SuitabilityAssessment>(
      `/v1/properties/${encodeURIComponent(propertyId)}/suitability`,
      { profile_id: profileId },
    ),
  createAssessment: (profileId: string, propertyId: string) =>
    post<Report>("/v1/assessments", {
      profile_id: profileId,
      property_id: propertyId,
      upload_ids: [],
    }),
  report: (id: string) => request<Report>(`/v1/reports/${encodeURIComponent(id)}`),
};
