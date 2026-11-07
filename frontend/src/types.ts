export const PAGES = [
  "home",
  "onboarding",
  "explore",
  "property",
  "report",
  "screening",
  "compare",
  "dashboard",
  "about",
] as const;

export type Page = (typeof PAGES)[number];

export type StatusType = "good" | "warn" | "info";
