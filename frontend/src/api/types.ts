// Types for the Haven API contract (contracts/openapi.yaml, version 0.1.1).
// Enum-typed strings are widened with `(string & {})`: the contract allows new enum values
// without notice, so the UI must tolerate (and display) values it doesn't know yet.

type Open<T extends string> = T | (string & {});

export type Origin = Open<"listing" | "public_data" | "user" | "model" | "estimate">;
export type EvidenceStatus = Open<"known" | "estimated" | "inferred" | "uncertain" | "insufficient">;
export type Outcome = Open<"meets" | "concern" | "unknown">;
export type BudgetComparison = Open<"within" | "over" | "unknown">;
export type Priority = Open<
  | "total_cost"
  | "step_free_access"
  | "lift_access"
  | "transport_access"
  | "travel_time"
  | "heating_cost"
>;

/** A fact with provenance. `value: null` always means `status: "insufficient"`. */
export interface Evidence<T> {
  value: T | null;
  origin: Origin;
  source: string;
  as_of: string | null;
  confidence: number | null;
  status: EvidenceStatus;
  note: string | null;
}

export interface RecurringCost {
  label: string;
  monthly_gbp: Evidence<number>;
}

export interface Property {
  id: string;
  title: string;
  illustrative: boolean;
  area: string | null;
  latitude: number | null;
  longitude: number | null;
  rent_pcm_gbp: Evidence<number>;
  bedrooms: Evidence<number>;
  property_type: Evidence<string>;
  floor_area_m2: Evidence<number>;
  council_tax_band: Evidence<string>;
  epc_rating: Evidence<string>;
  main_fuel: Evidence<string>;
  floor_level: Evidence<number>;
  has_lift: Evidence<boolean>;
  entrance_steps: Evidence<number>;
  other_recurring_costs: RecurringCost[];
}

export interface AccessRequirements {
  wheelchair_user: boolean;
  step_free_entrance_required: boolean;
  lift_required_above_floor: number | null;
  max_walk_to_stop_m: number | null;
}

export interface Destination {
  name: string;
  latitude: number;
  longitude: number;
  max_travel_minutes: number | null;
}

export interface ProfileInput {
  label: string;
  monthly_budget_gbp: number | null;
  priorities: Priority[];
  access: AccessRequirements;
  destinations: Destination[];
  other_recurring_costs: RecurringCost[];
}

export interface RenterProfile extends ProfileInput {
  id: string;
}

export interface CostLine {
  kind: string;
  label: string;
  monthly_gbp: Evidence<number>;
  low_gbp: number | null;
  high_gbp: number | null;
}

export interface CostBreakdown {
  property_id: string;
  profile_id: string | null;
  lines: CostLine[];
  total_monthly_gbp: Evidence<number>;
  total_low_gbp: number | null;
  total_high_gbp: number | null;
  budget_monthly_gbp: number | null;
  budget_comparison: BudgetComparison;
}

export interface CitedFact {
  name: string;
  evidence: Evidence<string | number | boolean>;
}

export interface Finding {
  id: string;
  rule_id: string;
  category: string;
  outcome: Outcome;
  title: string;
  reason: string;
  facts: CitedFact[];
  next_step: string | null;
}

export interface SuitabilityAssessment {
  property_id: string;
  profile_id: string;
  findings: Finding[];
}

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

export interface ReportSentence {
  text: string;
  cites: string[];
}

export interface ReportSection {
  heading: string;
  sentences: ReportSentence[];
}

export interface Report {
  id: string;
  created_at: string;
  illustrative: boolean;
  profile: RenterProfile;
  property: Property;
  cost: CostBreakdown | null;
  findings: Finding[];
  signals: Signal[];
  sections: ReportSection[];
  disclaimer: string;
}

export interface EnumOption {
  value: string;
  label: string;
}

export interface EnumsResponse {
  enums: Record<string, EnumOption[]>;
}
