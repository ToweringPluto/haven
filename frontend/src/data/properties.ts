import type { StatusType } from "../types";
import { IMAGES } from "./images";

export interface Property {
  id: string;
  name: string;
  area: string;
  /** Monthly rent in whole pounds. */
  rent: number;
  /** Estimated total monthly cost in whole pounds. */
  total: number;
  score: number;
  image: string;
  status: string;
  details: string;
  journey: string;
  transit: string;
}

export const PROPERTIES: Property[] = [
  {
    id: "leith-shore",
    name: "Bright one-bed near The Shore",
    area: "Leith, EH6",
    rent: 1095,
    total: 1341,
    score: 92,
    image: IMAGES.leith,
    status: "Suitable",
    details: "1 bed · 1 bath · Furnished",
    journey: "22 min to University of Edinburgh",
    transit: "Direct bus every 8 min",
  },
  {
    id: "marchmont-garden",
    name: "Spacious garden flat",
    area: "Marchmont, EH9",
    rent: 1250,
    total: 1512,
    score: 78,
    image: IMAGES.marchmont,
    status: "Potential concern",
    details: "2 bed · 1 bath · Unfurnished",
    journey: "12 min to University of Edinburgh",
    transit: "Easy walk or frequent bus",
  },
  {
    id: "stockbridge-top-floor",
    name: "Quiet top-floor apartment",
    area: "Stockbridge, EH4",
    rent: 1175,
    total: 1438,
    score: 74,
    image: IMAGES.stockbridge,
    status: "More information needed",
    details: "1 bed · 1 bath · Furnished",
    journey: "24 min to University of Edinburgh",
    transit: "1 change · buses every 10 min",
  },
];

/** The property the (currently static) detail and comparison pages describe. */
export const FEATURED_PROPERTY = PROPERTIES[0];

export const getProperty = (id: string) => PROPERTIES.find((p) => p.id === id);

export const scoreStatus = (score: number): StatusType =>
  score > 85 ? "good" : score > 75 ? "warn" : "info";
