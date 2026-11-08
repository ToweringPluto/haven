import type { Finding, Priority } from "../api/types";

/**
 * A lens colours every home by ONE indicator the renter picks. There is deliberately no
 * combined score: Haven shows how each home does on each thing, never which home is "best".
 */
export type LensId = "budget" | "heating" | "step_free" | "lift" | "transport" | "travel";

/** What a pin shows under the current lens. */
export type LensState = "meets" | "concern" | "unknown" | "not_checked" | "needs_profile" | "loading";

export interface Lens {
  id: LensId;
  label: string;
  short: string;
  /** The suitability rule this lens reads (none for budget, which compares estimated totals). */
  ruleId: string | null;
  priority: Priority;
}

export const LENSES: Lens[] = [
  { id: "budget", label: "Estimated total vs budget", short: "Budget", ruleId: null, priority: "total_cost" },
  { id: "heating", label: "Heating cost risk (EPC)", short: "Heating", ruleId: "epc_heating_cost_risk", priority: "heating_cost" },
  { id: "step_free", label: "Step-free entrance", short: "Step-free", ruleId: "step_free_entrance", priority: "step_free_access" },
  { id: "lift", label: "Lift for the floor", short: "Lift", ruleId: "lift_required_for_floor", priority: "lift_access" },
  { id: "transport", label: "Walk to a bus or tram stop", short: "Transport", ruleId: "walk_to_stop_within_limit", priority: "transport_access" },
  { id: "travel", label: "Travel time to your places", short: "Travel", ruleId: "travel_time_to_destinations", priority: "travel_time" },
];

/** The renter's own priorities first, then the rest in a fixed order. */
export function orderedLenses(priorities: Priority[]): Lens[] {
  const rank = (l: Lens) => {
    const i = priorities.indexOf(l.priority);
    return i === -1 ? 100 + LENSES.indexOf(l) : i;
  };
  return [...LENSES].sort((a, b) => rank(a) - rank(b));
}

export function findingFor(lens: Lens, findings: Finding[] | undefined): Finding | undefined {
  return lens.ruleId ? findings?.find((f) => f.rule_id === lens.ruleId) : undefined;
}

export function outcomeState(outcome: string): LensState {
  return outcome === "meets" ? "meets" : outcome === "concern" ? "concern" : "unknown";
}

export const STATE_COPY: Record<LensState, string> = {
  meets: "Meets",
  concern: "Possible concern",
  unknown: "Not enough evidence",
  not_checked: "Not checked for this profile",
  needs_profile: "Needs a renter profile",
  loading: "Checking…",
};
