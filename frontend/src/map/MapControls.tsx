import { useState } from "react";
import { Icon } from "../components/Icon";
import { ProfileBar } from "../components/ProfileBar";
import { BUDGET_RANGE } from "../data/onboarding";
import { formatGBP } from "../lib/format";
import { MUST_MEET, type MapFilters } from "./filters";
import { STATE_COPY, type Lens, type LensId, type LensState } from "./lenses";

export type PriceMode = "rent" | "total";

interface MapControlsProps {
  count: number;
  /** Homes that match the search but are hidden by the filters. */
  hiddenCount: number;
  filters: MapFilters;
  onFilters: (f: MapFilters) => void;
  areaOptions: string[];
  hasProfile: boolean;
  /** True while the filters are exactly what the renter's profile asks for. */
  matchesProfile: boolean;
  onResetFilters: () => void;
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
  const { lens, tally, priceMode, budget, filters, onFilters } = props;
  const toggle = <T,>(list: T[], item: T) =>
    list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
  const [open, setOpen] = useState(true);

  return (
    <section className={`map-controls${open ? "" : " is-collapsed"}`} aria-label="Map controls">
      <header className="map-controls-head">
        <div>
          <span className="section-kicker">Edinburgh rentals</span>
          <h1>
            {props.count} {props.count === 1 ? "home" : "homes"} on the map
          </h1>
          {props.hiddenCount > 0 && (
            <small className="map-hidden-count">{props.hiddenCount} hidden by your filters</small>
          )}
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

        <fieldset className="map-filters">
          <legend className="section-kicker">Show only</legend>
          {props.hasProfile && (
            <p className="map-filters-note">
              {props.matchesProfile ? (
                <>
                  <Icon name="check" size={14} /> Set from your renter profile.
                </>
              ) : (
                <button type="button" className="text-button" onClick={props.onResetFilters}>
                  Match my profile again
                </button>
              )}
            </p>
          )}

          <label className="filter-check">
            <input
              type="checkbox"
              checked={filters.withinBudget}
              onChange={() => onFilters({ ...filters, withinBudget: !filters.withinBudget })}
            />
            Within budget <small>(estimated monthly total)</small>
          </label>
          {(filters.withinBudget || lens.id === "budget") && (
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

          {MUST_MEET.map((m) => (
            <label key={m.id} className="filter-check">
              <input
                type="checkbox"
                checked={filters.mustMeet.includes(m.id)}
                disabled={!props.hasProfile}
                onChange={() => onFilters({ ...filters, mustMeet: toggle(filters.mustMeet, m.id) })}
              />
              {m.label}
            </label>
          ))}
          {!props.hasProfile && (
            <small className="map-filters-hint">Access and travel filters need a renter profile.</small>
          )}

          <div className="area-chips" role="group" aria-label="Areas">
            <button
              type="button"
              className={filters.areas.length === 0 ? "is-on" : ""}
              aria-pressed={filters.areas.length === 0}
              onClick={() => onFilters({ ...filters, areas: [] })}
            >
              All areas
            </button>
            {props.areaOptions.map((a) => (
              <button
                key={a}
                type="button"
                className={filters.areas.includes(a) ? "is-on" : ""}
                aria-pressed={filters.areas.includes(a)}
                onClick={() => onFilters({ ...filters, areas: toggle(filters.areas, a) })}
              >
                {a}
              </button>
            ))}
          </div>
          <small className="map-filters-hint">
            Homes Haven isn’t sure about stay on the map; only clear concerns are hidden.
          </small>
          {props.count === 0 && props.hiddenCount > 0 && (
            <p className="map-filters-empty" role="status">
              No homes match all of these. Try turning a filter off.
            </p>
          )}
        </fieldset>

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
