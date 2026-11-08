import type { Property } from "../api/types";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { displayTitle, formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useShortlist } from "../state/shortlist";
import { STATE_COPY, type Lens, type LensState } from "./lenses";
import type { HomeData } from "./useMapData";

export const MAX_COMPARE = 3;

interface CompareTrayProps {
  properties: Property[];
  homes: Record<string, HomeData>;
  lens: Lens;
  stateFor: (id: string) => LensState;
  onFocus: (id: string) => void;
}

/** The homes picked for comparison, side by side along the bottom of the map. */
export function CompareTray({ properties, homes, lens, stateFor, onFocus }: CompareTrayProps) {
  const { go } = useNavigation();
  const { compare, toggleCompare, clearCompare } = useShortlist();
  const chosen = compare
    .map((id) => properties.find((p) => p.id === id))
    .filter((p): p is Property => !!p);
  if (chosen.length === 0) return null;

  return (
    <section className="compare-tray" aria-label="Homes to compare">
      <div className="compare-tray-cards">
        {chosen.map((p) => {
          const cost = homes[p.id]?.cost;
          const total = cost?.status === "ok" ? cost.data.total_monthly_gbp.value : null;
          const state = stateFor(p.id);
          return (
            <article key={p.id} className="compare-card">
              <button type="button" className="compare-card-main" onClick={() => onFocus(p.id)}>
                <span>{p.area}</span>
                <b>{displayTitle(p.title)}</b>
                <span className="compare-card-total">
                  {total !== null ? `${formatGBP(total)} est. a month` : "Total not available"}
                </span>
                <span className={`lens-chip lens-chip--${state}`}>
                  {lens.short}: {STATE_COPY[state]}
                </span>
              </button>
              <button
                type="button"
                className="compare-card-remove"
                onClick={() => toggleCompare(p.id)}
                aria-label={`Remove ${displayTitle(p.title)} from comparison`}
              >
                <Icon name="x" size={14} />
              </button>
            </article>
          );
        })}
      </div>
      <div className="compare-tray-actions">
        <button type="button" className="text-button" onClick={clearCompare}>
          Clear
        </button>
        <Button onClick={() => go("compare")} disabled={chosen.length < 2}>
          Compare side by side <Icon name="arrow" size={16} />
        </Button>
      </div>
    </section>
  );
}
