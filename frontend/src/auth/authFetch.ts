import { useCallback } from "react";
import { useAuth } from "./AuthProvider";
import { API_BASE_URL } from "./config";

export const SIGN_IN_MESSAGE = "Sign in to use this feature";

export type ApiResult<T> =
  | { status: "ok"; data: T }
  | { status: "signin"; message: string }
  | { status: "error"; message: string; httpStatus?: number };

/** FastAPI errors look like `{"detail": "..."}`; fall back to a generic message otherwise. */
async function errorMessage(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Non-JSON error body.
  }
  return `Request failed (${res.status})`;
}

/**
 * Calls the API with `Authorization: Bearer <token>`. Never throws: missing tokens and 401s
 * become `{status: "signin"}`, everything else that goes wrong becomes `{status: "error"}`.
 */
export async function authFetch<T>(
  getAccessToken: () => Promise<string | null>,
  path: string,
  init: RequestInit = {},
  parse: (res: Response) => Promise<T> = (res) => res.json() as Promise<T>,
): Promise<ApiResult<T>> {
  const token = await getAccessToken();
  if (!token) return { status: "signin", message: SIGN_IN_MESSAGE };

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);

  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
    if (res.status === 401) return { status: "signin", message: SIGN_IN_MESSAGE };
    if (!res.ok) return { status: "error", message: await errorMessage(res), httpStatus: res.status };
    return { status: "ok", data: await parse(res) };
  } catch {
    return { status: "error", message: "Couldn’t reach the Haven service." };
  }
}

/** `authFetch` bound to the current user's token. */
export function useAuthFetch() {
  const { getAccessToken } = useAuth();
  return useCallback(
    <T,>(path: string, init?: RequestInit, parse?: (res: Response) => Promise<T>) =>
      authFetch<T>(getAccessToken, path, init, parse),
    [getAccessToken],
  );
}
