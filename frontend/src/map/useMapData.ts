import { useEffect, useState } from "react";
import { api, type Loaded } from "../api/client";
import type { CostBreakdown, Property, SuitabilityAssessment } from "../api/types";
import type { LoadState } from "../api/useLoad";

export interface HomeData {
  cost: LoadState<CostBreakdown>;
  /** Absent when there's no renter profile (checks need one). */
  suitability: LoadState<SuitabilityAssessment> | null;
}

/** Runs `tasks` with at most `limit` in flight, so a map of homes doesn't flood the API. */
async function pool(tasks: (() => Promise<void>)[], limit: number) {
  let next = 0;
  const worker = async () => {
    while (next < tasks.length) await tasks[next++]();
  };
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker));
}

/**
 * The true monthly cost (and, with a profile, the requirement checks) for every home on the
 * map. Results stream in as they arrive; a profile change starts over and drops late replies.
 */
export function useMapData(properties: Property[] | null, profileId: string | null) {
  const [data, setData] = useState<Record<string, HomeData>>({});
  const ids = properties?.map((p) => p.id).join(",") ?? "";

  useEffect(() => {
    if (!properties) return;
    let current = true;
    setData(
      Object.fromEntries(
        properties.map((p) => [
          p.id,
          { cost: { status: "loading" }, suitability: profileId ? { status: "loading" } : null },
        ]),
      ),
    );
    const put = (id: string, patch: Partial<HomeData>) =>
      current && setData((d) => ({ ...d, [id]: { ...d[id], ...patch } }));

    const tasks = properties.flatMap((p) => {
      const cost = async () => {
        const res: Loaded<CostBreakdown> = await api.cost(p.id, profileId);
        put(p.id, { cost: res });
      };
      const checks = async () => {
        const res = await api.suitability(p.id, profileId!);
        put(p.id, { suitability: res });
      };
      return profileId ? [cost, checks] : [cost];
    });
    void pool(tasks, 4);
    return () => {
      current = false;
    };
    // `ids` captures the property list.
  }, [ids, profileId]);

  return data;
}
