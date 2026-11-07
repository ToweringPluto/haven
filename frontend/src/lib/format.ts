const gbp = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

/** Formats a whole-pound amount, e.g. 1095 → "£1,095". */
export const formatGBP = (amount: number) => gbp.format(Math.round(amount));

const ORDINAL_SUFFIX: Record<number, string> = { 1: "st", 2: "nd", 3: "rd" };

/** 1 → "1st", 2 → "2nd", 11 → "11th", 23 → "23rd". */
const ordinal = (n: number) => {
  const teen = n % 100 >= 11 && n % 100 <= 13;
  return `${n}${teen ? "th" : (ORDINAL_SUFFIX[n % 10] ?? "th")}`;
};

/** "Illustrative property — not a real listing: 2-bed flat, Leith" → "2-bed flat, Leith". */
export const ILLUSTRATIVE_PREFIX = /^Illustrative property\s*[—–-]\s*not a real listing:\s*/i;
export const displayTitle = (title: string) => title.replace(ILLUSTRATIVE_PREFIX, "");

type Label = (enumName: string, value: string) => string;

const FACT_NAMES: Record<string, string> = {
  rent_pcm_gbp: "Rent",
  bedrooms: "Bedrooms",
  property_type: "Property type",
  floor_area_m2: "Floor area",
  council_tax_band: "Council tax band",
  epc_rating: "EPC rating",
  main_fuel: "Main heating fuel",
  floor_level: "Floor",
  has_lift: "Lift",
  entrance_steps: "Entrance steps",
  total_monthly_gbp: "Estimated total",
  budget_monthly_gbp: "Your budget",
  walk_to_stop_m: "Walk to nearest stop",
  monthly_budget_gbp: "Your budget",
};

export const factName = (name: string) =>
  FACT_NAMES[name] ?? name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Human-readable value of a named fact (property field or a finding's cited fact). */
export function formatFact(name: string, value: string | number | boolean, label: Label): string {
  switch (name) {
    case "bedrooms":
      return `${value} bed`;
    case "floor_area_m2":
      return `${value} m²`;
    case "floor_level":
      return value === 0 ? "Ground floor" : `${ordinal(Number(value))} floor`;
    case "has_lift":
      return value ? "Lift" : "No lift";
    case "entrance_steps":
      return value === 0 ? "No entrance steps" : `${value} entrance step${value === 1 ? "" : "s"}`;
    case "property_type":
      return label("property_type", String(value));
    case "council_tax_band":
      return label("council_tax_band", String(value));
    case "epc_rating":
      return label("epc_band", String(value));
    case "main_fuel":
      return label("main_fuel", String(value));
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (name.endsWith("_gbp")) return formatGBP(value);
    if (name.endsWith("_minutes")) return `${value} min`;
    if (name.endsWith("_m")) return `${value} m`;
  }
  return String(value);
}
