import type { AccessRequirements, Destination, Priority, ProfileInput } from "../api/types";

// Every option here maps to something the backend can check (ProfileInput in the contract),
// so the renter is never asked about a need Haven silently ignores.

/** Areas of the seed properties. Used client-side only, to list preferred areas first. */
export const AREA_OPTIONS = [
  "Leith",
  "Dalry",
  "Sighthill",
  "Wester Hailes",
  "Marchmont",
  "Bruntsfield",
  "Old Town",
  "Portobello",
  "Craigleith",
  "Gorgie",
  "Gilmerton",
];

export type AccessKey = "wheelchair_user" | "step_free" | "lift" | "short_walk" | "none";

export const ACCESS_OPTIONS: { key: AccessKey; label: string }[] = [
  { key: "wheelchair_user", label: "I use a wheelchair" },
  { key: "step_free", label: "Step-free entrance" },
  { key: "lift", label: "A lift if it’s above the ground floor" },
  { key: "short_walk", label: "A bus or tram stop within 400 m" },
  { key: "none", label: "No specific needs" },
];

export function accessRequirements(keys: AccessKey[]): AccessRequirements {
  const has = (k: AccessKey) => keys.includes(k);
  return {
    wheelchair_user: has("wheelchair_user"),
    step_free_entrance_required: has("step_free") || has("wheelchair_user"),
    lift_required_above_floor: has("lift") || has("wheelchair_user") ? 0 : null,
    max_walk_to_stop_m: has("short_walk") ? 400 : null,
  };
}

export function accessKeys(access: AccessRequirements): AccessKey[] {
  const keys: AccessKey[] = [];
  if (access.wheelchair_user) keys.push("wheelchair_user");
  if (access.step_free_entrance_required) keys.push("step_free");
  if (access.lift_required_above_floor !== null) keys.push("lift");
  if (access.max_walk_to_stop_m !== null) keys.push("short_walk");
  return keys;
}

/** Display order; labels come from GET /v1/meta/enums. */
export const PRIORITY_OPTIONS: Priority[] = [
  "total_cost",
  "heating_cost",
  "step_free_access",
  "lift_access",
  "transport_access",
  "travel_time",
];

/**
 * Destinations need coordinates and Haven has no geocoder yet, so renters pick from known
 * places. Coordinates are approximate building locations.
 */
export const DESTINATIONS: (Omit<Destination, "max_travel_minutes"> & { id: string })[] = [
  { id: "uoe-central", name: "University of Edinburgh Central Area", latitude: 55.9445, longitude: -3.1892 },
  { id: "royal-infirmary", name: "Royal Infirmary of Edinburgh", latitude: 55.9216, longitude: -3.1347 },
  { id: "western-general", name: "Western General Hospital", latitude: 55.962, longitude: -3.234 },
  { id: "heriot-watt", name: "Heriot-Watt University, Riccarton", latitude: 55.9097, longitude: -3.322 },
  { id: "napier-merchiston", name: "Edinburgh Napier University, Merchiston", latitude: 55.933, longitude: -3.213 },
  { id: "waverley", name: "Edinburgh Waverley station", latitude: 55.952, longitude: -3.189 },
  { id: "edinburgh-park", name: "Edinburgh Park", latitude: 55.927, longitude: -3.307 },
];

export const BUDGET_RANGE = { min: 500, max: 2500, step: 50 } as const;

export interface ExampleRenter {
  id: string;
  name: string;
  blurb: string;
  /**
   * Set for the lower-budget demo renters, which aren't stored on the server: choosing one
   * creates a profile from these answers. The others are the server's sample profiles.
   */
  preset?: ProfileInput;
}

const preset = (
  label: string,
  budget: number,
  priorities: Priority[],
  access: AccessKey[] = [],
): ProfileInput => ({
  label,
  monthly_budget_gbp: budget,
  priorities,
  access: accessRequirements(access),
  destinations: [],
  other_recurring_costs: [],
  preferred_areas: [],
});

/** Example renters for exploring without filling in the profile builder. */
export const PERSONAS: ExampleRenter[] = [
  {
    id: "persona-wheelchair-user",
    name: "Wheelchair user",
    blurb: "Needs step-free access and a lift; travels to the Royal Infirmary.",
  },
  {
    id: "persona-student",
    name: "Student",
    blurb: "Budget of £900; cares about cost and the journey to university.",
  },
  {
    id: "persona-tight-budget",
    name: "Tight budget",
    blurb: "Budget of £1,000; total cost and heating bills come first.",
  },
  {
    id: "demo-low-budget",
    name: "Low budget",
    blurb: "£750 a month all in; total cost and heating bills come first.",
    preset: preset("Low budget", 750, ["total_cost", "heating_cost"]),
  },
  {
    id: "demo-low-budget-step-free",
    name: "Low budget, step-free",
    blurb: "£800 a month; needs a step-free entrance and a bus stop within 400 m.",
    preset: preset(
      "Low budget, step-free",
      800,
      ["total_cost", "step_free_access", "transport_access"],
      ["step_free", "short_walk"],
    ),
  },
];
