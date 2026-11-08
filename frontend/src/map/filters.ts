import type { ProfileDraft } from "../state/renterProfile";
import type { LensId, LensState } from "./lenses";

/** Requirement checks a renter can make a must-have on the map. */
export const MUST_MEET: { id: LensId; label: string }[] = [
  { id: "step_free", label: "Step-free entrance" },
  { id: "lift", label: "Lift for the floor" },
  { id: "transport", label: "Bus or tram stop within walking distance" },
  { id: "travel", label: "Travel time to your places" },
];

/**
 * What the map hides. Filters only ever hide a home Haven found a concern with: a home it
 * can't be sure about stays visible, so a gap in the data never hides a possible match.
 */
export interface MapFilters {
  withinBudget: boolean;
  /** Empty means every area. */
  areas: string[];
  mustMeet: LensId[];
}

/** The filters that match what the renter told us in their profile. */
export function filtersFromProfile(draft: ProfileDraft, hasProfile: boolean): MapFilters {
  const access = new Set(draft.access);
  const wheelchair = access.has("wheelchair_user");
  const mustMeet: LensId[] = [];
  if (hasProfile) {
    if (wheelchair || access.has("step_free")) mustMeet.push("step_free");
    if (wheelchair || access.has("lift")) mustMeet.push("lift");
    if (access.has("short_walk")) mustMeet.push("transport");
    if (draft.destinationIds.length > 0) mustMeet.push("travel");
  }
  return { withinBudget: hasProfile, areas: [...draft.areas], mustMeet };
}

export const sameFilters = (a: MapFilters, b: MapFilters) =>
  a.withinBudget === b.withinBudget &&
  [...a.areas].sort().join("|") === [...b.areas].sort().join("|") &&
  [...a.mustMeet].sort().join("|") === [...b.mustMeet].sort().join("|");

/** True when the home should stay on the map. `stateOf` gives the home's state under a lens. */
export function passesFilters(
  filters: MapFilters,
  area: string | null,
  stateOf: (lens: LensId) => LensState,
): boolean {
  if (filters.areas.length > 0 && !filters.areas.includes(area ?? "")) return false;
  if (filters.withinBudget && stateOf("budget") === "concern") return false;
  return filters.mustMeet.every((id) => stateOf(id) !== "concern");
}
