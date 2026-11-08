import { useState } from "react";
import { Icon } from "../components/Icon";
import { ProfileBar } from "../components/ProfileBar";
import { BUDGET_RANGE } from "../data/onboarding";
import { formatGBP } from "../lib/format";
import { STATE_COPY, type Lens, type LensId, type LensState } from "./lenses";

export type PriceMode = "rent" | "total";

interface MapControlsProps {
  count: number;
  query: string;
  onQuery: (q: string) => void;
  priceMode: PriceMode;
  onPriceMode: (m: PriceMode) => void;
  lenses: Lens[];
  lens: Lens;
  onLens: (id: LensId) => void;
  budget: number;
  onBudget: (b: number) => void;
  /** How many homes are in each state under the current lens. */
  tally: Partial<Record<LensState, number>>;
  onOverview: () => void;
  view: "map" | "list";
  onView: (v: "map" | "list") => void;
}

const LEGEND: LensState[] = ["meets", "concern", "unknown", "not_checked", "needs_profile"];

/** The floating control card: whose needs, which price, which single indicator to colour by. */
export function MapControls(props: MapControlsProps) {
  const { lens, tally, priceMode, budget } = props;
  const [open, setOpen] = useState(true);

  return (
    <section className={`map-controls${open ? "" : " is-collapsed"}`} aria-label="Map controls">
      <header className="map-controls-head">
        <div>
          <span className="section-kicker">Edinburgh rentals</span>
          <h1>
            {props.count} {props.count === 1 ? "home" : "homes"} on the map
          </h1>
        </div>
        <button
          type="button"
          className="map-controls-toggle"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={open ? "Hide controls" : "Show controls"}
        >
          <Icon name={open ? "x" : "menu"} size={18} />
        </button>
      </header>

      <div className="map-controls-body">
        <p className="map-sample-note">
          <Icon name="info" size={15} /> Every home here is an illustrative example, not a real listing.
        </p>

        <ProfileBar />

        <div className="search-box" role="search">
          <Icon name="search" />
          <input
            aria-label="Filter by area or description"
            placeholder="Filter by area, e.g. Leith"
            value={props.query}
            onChange={(e) => props.onQuery(e.target.value)}
          />
        </div>

        <fieldset className="segmented">
          <legend className="section-kicker">Price on the pins</legend>
          <label className={priceMode === "rent" ? "is-on" : ""}>
            <input type="radio" name="price-mode" checked={priceMode === "rent"} onChange={() => props.onPriceMode("rent")} />
            Rent
          </label>
          <label className={priceMode === "total" ? "is-on" : ""}>
            <input type="radio" name="price-mode" checked={priceMode === "total"} onChange={() => props.onPriceMode("total")} />
            True monthly cost <small>est.</small>
          </label>
        </fieldset>

        <fieldset className="lens-picker">
          <legend className="section-kicker">Colour homes by one thing</legend>
          <div className="lens-options">
            {props.lenses.map((l) => (
              <label key={l.id} className={l.id === lens.id ? "is-on" : ""}>
                <input type="radio" name="lens" checked={l.id === lens.id} onChange={() => props.onLens(l.id)} />
                {l.short}
              </label>
            ))}
          </div>
          <p className="lens-caption">
            <b>{lens.label}.</b>{" "}
            {lens.id === "budget"
              ? "Compares each home’s estimated monthly total with the budget below. Estimates, not quotes."
              : "From Haven’s requirement check for the selected renter. One indicator at a time: there is no overall score."}
          </p>
        </fieldset>

        {lens.id === "budget" && (
          <label className="budget-horizon">
            <span>
              Budget <b>{formatGBP(budget)}</b> a month
            </span>
            <input
              type="range"
              min={BUDGET_RANGE.min}
              max={BUDGET_RANGE.max}
              step={BUDGET_RANGE.step}
              value={budget}
              onChange={(e) => props.onBudget(Number(e.target.value))}
              style={{ ["--fill" as string]: `${((budget - BUDGET_RANGE.min) / (BUDGET_RANGE.max - BUDGET_RANGE.min)) * 100}%` }}
            />
          </label>
        )}

        <ul className="map-legend" aria-label="Legend">
          {LEGEND.filter((s) => tally[s]).map((s) => (
            <li key={s}>
              <i className={`legend-dot legend-dot--${s}`} />
              {STATE_COPY[s]} <b>{tally[s]}</b>
            </li>
          ))}
          {tally.loading ? <li className="legend-loading">Checking {tally.loading}…</li> : null}
        </ul>

        <div className="map-controls-foot">
          <button type="button" className="text-button" onClick={props.onOverview}>
            <Icon name="map" size={16} /> Whole city
          </button>
          <div className="segmented segmented--small" role="group" aria-label="View">
            <button type="button" className={props.view === "map" ? "is-on" : ""} aria-pressed={props.view === "map"} onClick={() => props.onView("map")}>
              Map
            </button>
            <button type="button" className={props.view === "list" ? "is-on" : ""} aria-pressed={props.view === "list"} onClick={() => props.onView("list")}>
              List
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
