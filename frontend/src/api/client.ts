import { API_BASE_URL } from "../auth/config";
import type {
  CostBreakdown,
  EnumsResponse,
  ProfileInput,
  Property,
  RenterProfile,
  Report,
  SuitabilityAssessment,
  Upload,
  UploadKind,
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

async function request<T>(
  path: string,
  init?: RequestInit,
  token?: string | null,
): Promise<Loaded<T>> {
  const headers: Record<string, string> = { Accept: "application/json" };
  // JSON bodies are strings; FormData sets its own multipart Content-Type.
  if (typeof init?.body === "string") headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
    if (res.status === 204) return { status: "ok", data: undefined as T };
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

const post = <T>(path: string, body: unknown, token?: string | null) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) }, token);

export const api = {
  enums: () => request<EnumsResponse>("/v1/meta/enums"),
  properties: () => request<{ items: Property[] }>("/v1/properties"),
  property: (id: string) => request<Property>(`/v1/properties/${encodeURIComponent(id)}`),
  profile: (id: string) => request<RenterProfile>(`/v1/profiles/${encodeURIComponent(id)}`),
  /** With a token the profile belongs to the signed-in user; without one it's private to its id. */
  createProfile: (input: ProfileInput, token?: string | null) =>
    post<RenterProfile>("/v1/profiles", input, token),
  cost: (propertyId: string, profileId: string | null) =>
    post<CostBreakdown>(`/v1/properties/${encodeURIComponent(propertyId)}/cost`, {
      profile_id: profileId,
    }),
  suitability: (propertyId: string, profileId: string) =>
    post<SuitabilityAssessment>(
      `/v1/properties/${encodeURIComponent(propertyId)}/suitability`,
      { profile_id: profileId },
    ),
  createAssessment: (profileId: string, propertyId: string, uploadIds: string[] = []) =>
    post<Report>("/v1/assessments", {
      profile_id: profileId,
      property_id: propertyId,
      upload_ids: uploadIds,
    }),
  uploadFile: (kind: UploadKind, file: File, propertyId: string | null) => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    if (propertyId) form.append("property_id", propertyId);
    return request<Upload>("/v1/uploads", { method: "POST", body: form });
  },
  deleteUpload: (id: string) =>
    request<void>(`/v1/uploads/${encodeURIComponent(id)}`, { method: "DELETE" }),
  report: (id: string) => request<Report>(`/v1/reports/${encodeURIComponent(id)}`),
};
