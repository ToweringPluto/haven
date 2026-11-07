import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { LoadProblem } from "../components/LoadProblem";
import { ProfileBar } from "../components/ProfileBar";
import { PropertyCard } from "../components/PropertyCard";
import { displayTitle } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

export default function Explore() {
  const { go } = useNavigation();
  const { draft } = useRenterProfile();
  const { compare, clearCompare } = useShortlist();
  const [query, setQuery] = useState("");
  const [properties, reload] = useLoad("all", api.properties);

  const shown = useMemo(() => {
    if (properties.status !== "ok") return [];
    const q = query.trim().toLowerCase();
    const matches = properties.data.items.filter(
      (p) =>
        !q ||
        displayTitle(p.title).toLowerCase().includes(q) ||
        (p.area ?? "").toLowerCase().includes(q),
    );
    // Preferred areas first; otherwise keep the server's order. No ranking by "fit".
    const preferred = (area: string | null) => draft.areas.includes(area ?? "");
    return [...matches].sort((a, b) => Number(preferred(b.area)) - Number(preferred(a.area)));
  }, [properties, query, draft.areas]);

  return (
    <main className="explore-page shell">
      <div className="explore-title">
        <div>
          <span className="section-kicker">Edinburgh rentals</span>
          <h1>Homes to look into</h1>
          <p>
            Every figure shows where it comes from. Open a home for its true monthly cost and the
            checks against your requirements.
          </p>
        </div>
      </div>

      <ProfileBar />

      <div className="search-row">
        <div className="search-box" role="search">
          <Icon name="search" />
          <input
            aria-label="Filter by area or description"
            placeholder="Filter by area, e.g. Leith"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {draft.areas.length > 0 && (
        <p className="list-note">Showing {draft.areas.join(", ")} first.</p>
      )}

      {properties.status === "loading" && <p className="list-note">Loading homes…</p>}
      {properties.status !== "loading" && properties.status !== "ok" && (
        <LoadProblem result={properties} onRetry={reload} />
      )}
      {properties.status === "ok" && (
        <>
          <p className="list-note">
            {shown.length} {shown.length === 1 ? "home" : "homes"}. All are illustrative examples,
            not real listings.
          </p>
          <div className="property-grid">
            {shown.map((p) => (
              <PropertyCard key={p.id} property={p} />
            ))}
          </div>
        </>
      )}

      {compare.length > 0 && (
        <div className="compare-bar">
          <span>
            <b>{compare.length}</b> {compare.length === 1 ? "home" : "homes"} selected
          </span>
          <div>
            <button type="button" onClick={clearCompare}>
              Clear
            </button>
            <Button
              onClick={() => go("compare")}
              className={compare.length < 2 ? "disabled" : ""}
              disabled={compare.length < 2}
            >
              Compare side by side <Icon name="arrow" />
            </Button>
          </div>
        </div>
      )}
    </main>
  );
}
