import { API_BASE_URL } from "../auth/config";
import type {
  CostBreakdown,
  DeletedData,
  EnumsResponse,
  ProfileInput,
  Property,
  RenterProfile,
  Report,
  ReportSummary,
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
    if (res.status === 401) return { status: "error", message: SIGN_IN_NEEDED };
    return { status: "error", message };
  } catch {
    return {
      status: "error",
      message: "Couldn’t reach the Haven service. Is the backend running?",
    };
  }
}

/** Shown when a signed-in endpoint is called without a (valid) token. */
export const SIGN_IN_NEEDED = "Please sign in to use this.";

type Token = string | null | undefined;

const post = <T>(path: string, body: unknown, token?: Token) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) }, token);
const put = <T>(path: string, body: unknown, token: Token) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) }, token);
const del = (path: string, token: Token) => request<void>(path, { method: "DELETE" }, token);
const id = encodeURIComponent;

export const api = {
  enums: () => request<EnumsResponse>("/v1/meta/enums"),
  properties: () => request<{ items: Property[] }>("/v1/properties"),
  property: (propertyId: string) => request<Property>(`/v1/properties/${id(propertyId)}`),

  // --- profiles: public to read; signed in to own, edit or delete -----------------------
  profile: (profileId: string) => request<RenterProfile>(`/v1/profiles/${id(profileId)}`),
  /** The sample profiles plus, with a token, the signed-in user's own. */
  profiles: (token: Token) => request<{ items: RenterProfile[] }>("/v1/profiles", {}, token),
  /** With a token the profile belongs to the signed-in user; without one it's private to its id. */
  createProfile: (input: ProfileInput, token: Token) =>
    post<RenterProfile>("/v1/profiles", input, token),
  updateProfile: (profileId: string, input: ProfileInput, token: Token) =>
    put<RenterProfile>(`/v1/profiles/${id(profileId)}`, input, token),
  deleteProfile: (profileId: string, token: Token) => del(`/v1/profiles/${id(profileId)}`, token),

  // --- checks (public) ------------------------------------------------------------------
  cost: (propertyId: string, profileId: string | null) =>
    post<CostBreakdown>(`/v1/properties/${id(propertyId)}/cost`, { profile_id: profileId }),
  suitability: (propertyId: string, profileId: string) =>
    post<SuitabilityAssessment>(`/v1/properties/${id(propertyId)}/suitability`, {
      profile_id: profileId,
    }),

  // --- signed in: uploads, reports, saved homes, deleting data --------------------------
  createAssessment: (profileId: string, propertyId: string, uploadIds: string[], token: Token) =>
    post<Report>(
      "/v1/assessments",
      { profile_id: profileId, property_id: propertyId, upload_ids: uploadIds },
      token,
    ),
  uploadFile: (kind: UploadKind, file: File, propertyId: string | null, token: Token) => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    if (propertyId) form.append("property_id", propertyId);
    return request<Upload>("/v1/uploads", { method: "POST", body: form }, token);
  },
  myUploads: (propertyId: string | null, token: Token) =>
    request<{ items: Upload[] }>(
      propertyId ? `/v1/uploads?property_id=${id(propertyId)}` : "/v1/uploads",
      {},
      token,
    ),
  deleteUpload: (uploadId: string, token: Token) => del(`/v1/uploads/${id(uploadId)}`, token),
  /** Example reports are public; a saved report needs its owner's token. */
  report: (reportId: string, token?: Token) =>
    request<Report>(`/v1/reports/${id(reportId)}`, {}, token),
  myReports: (token: Token) => request<{ items: ReportSummary[] }>("/v1/reports", {}, token),
  savedHomes: (token: Token) => request<{ property_ids: string[] }>("/v1/me/saved-homes", {}, token),
  setSavedHomes: (propertyIds: string[], token: Token) =>
    put<{ property_ids: string[] }>("/v1/me/saved-homes", { property_ids: propertyIds }, token),
  deleteMyData: (token: Token) => request<DeletedData>("/v1/me", { method: "DELETE" }, token),
};
