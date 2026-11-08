import { useCallback, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { api } from "./client";
import type { Upload } from "./types";

/**
 * Creates a report (`POST /v1/assessments`) for a home and renter, including the files
 * attached to that home, as the signed-in renter. Resolves to the new report's id, or null with `error` set.
 */
export function useCreateReport(unavailableHint?: string) {
  const { getAccessToken } = useAuth();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = useCallback(
    async (profileId: string, propertyId: string, uploads: Upload[]) => {
      setCreating(true);
      setError(null);
      const res = await api.createAssessment(
        profileId,
        propertyId,
        uploads.filter((u) => u.property_id === propertyId).map((u) => u.id),
        await getAccessToken(),
      );
      setCreating(false);
      if (res.status === "ok") return res.data.id;
      setError(
        res.status === "unavailable" && unavailableHint
          ? `${res.message} ${unavailableHint}`
          : res.message,
      );
      return null;
    },
    [unavailableHint, getAccessToken],
  );

  return { create, creating, error };
}
