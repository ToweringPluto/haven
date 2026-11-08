import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { Property, Upload } from "../api/types";
import { useLoad } from "../api/useLoad";
import { Icon } from "../components/Icon";
import { LoadProblem } from "../components/LoadProblem";
import { PropertyCard } from "../components/PropertyCard";
import { DESTINATIONS } from "../data/onboarding";
import { displayTitle } from "../lib/format";
import "../map/map.css";
import { CompareTray } from "../map/CompareTray";
import { HavenMap, type PinView, type PlaceView } from "../map/HavenMap";
import { findingFor, LENSES, orderedLenses, outcomeState, type Lens, type LensId, type LensState } from "../map/lenses";
import { MapControls, type PriceMode } from "../map/MapControls";
import { PropertyDrawer } from "../map/PropertyDrawer";
import { useMapData, type HomeData } from "../map/useMapData";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

/** One indicator, one home. Never combined into a score. */
function lensState(lens: Lens, home: HomeData | undefined, budget: number, hasProfile: boolean): LensState {
  if (!home) return "loading";
  if (lens.id === "budget") {
    if (home.cost.status === "loading") return "loading";
    if (home.cost.status !== "ok") return "unknown";
    const total = home.cost.data.total_monthly_gbp.value;
    return total === null ? "unknown" : total <= budget ? "meets" : "concern";
  }
  if (!hasProfile || !home.suitability) return "needs_profile";
  if (home.suitability.status === "loading") return "loading";
  if (home.suitability.status !== "ok") return "unknown";
  const finding = findingFor(lens, home.suitability.data.findings);
  return finding ? outcomeState(finding.outcome) : "not_checked";
}

const matchesQuery = (p: Property, q: string) =>
  !q || displayTitle(p.title).toLowerCase().includes(q) || (p.area ?? "").toLowerCase().includes(q);

export default function Explore() {
  const { saved: profile, draft } = useRenterProfile();
  const { compare, saved } = useShortlist();
  const profileId = profile?.id ?? null;
  const [properties, reload] = useLoad("all", api.properties);
  const items = properties.status === "ok" ? properties.data.items : null;
  const homes = useMapData(items, profileId);

  const [view, setView] = useState<"map" | "list">("map");
  const [query, setQuery] = useState("");
  const [priceMode, setPriceMode] = useState<PriceMode>("rent");
  const [lensId, setLensId] = useState<LensId>("budget");
  const [budget, setBudget] = useState(draft.budget);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [overviewNonce, setOverviewNonce] = useState(0);
  const [reveal, setReveal] = useState(false);
  const touchedPrice = useRef(false);
  const narrow = useMediaQuery("(max-width: 760px)");

  useEffect(() => setBudget(draft.budget), [draft.budget]);

  const lenses = useMemo(() => orderedLenses(draft.priorities), [draft.priorities]);
  const lens = LENSES.find((l) => l.id === lensId) ?? LENSES[0];

  const located = useMemo(
    () => (items ?? []).filter((p) => p.latitude !== null && p.longitude !== null),
    [items],
  );
  const q = query.trim().toLowerCase();
  const shown = useMemo(() => {
    const preferred = (area: string | null) => draft.areas.includes(area ?? "");
    return located
      .filter((p) => matchesQuery(p, q))
      .sort((a, b) => Number(preferred(b.area)) - Number(preferred(a.area)));
  }, [located, q, draft.areas]);

  const stateFor = useCallback(
    (id: string) => lensState(lens, homes[id], budget, profileId !== null),
    [lens, homes, budget, profileId],
  );

  const pins: PinView[] = useMemo(
    () =>
      shown.map((p) => {
        const cost = homes[p.id]?.cost;
        const total = cost?.status === "ok" ? cost.data.total_monthly_gbp.value : null;
        const wantsTotal = priceMode === "total" && cost?.status !== "loading";
        const state = stateFor(p.id);
        return {
          id: p.id,
          lngLat: [p.longitude!, p.latitude!],
          title: displayTitle(p.title),
          area: p.area ?? "Edinburgh",
          price: wantsTotal ? total : p.rent_pcm_gbp.value,
          priceIsEstimate: wantsTotal,
          state,
          faded: lens.id === "budget" && state === "concern",
          saved: saved.includes(p.id),
          inCompare: compare.includes(p.id),
        };
      }),
    [shown, homes, priceMode, stateFor, lens.id, saved, compare],
  );

  const tally = useMemo(() => {
    const t: Partial<Record<LensState, number>> = {};
    pins.forEach((p) => (t[p.state] = (t[p.state] ?? 0) + 1));
    return t;
  }, [pins]);

  const places: PlaceView[] = useMemo(
    () =>
      DESTINATIONS.filter((d) => draft.destinationIds.includes(d.id)).map((d) => ({
        name: d.name,
        lngLat: [d.longitude, d.latitude],
      })),
    [draft.destinationIds],
  );

  // The signature moment: once the city has settled, every rent counts up to what living
  // there is estimated to cost each month. Only once, and never over the renter's own choice.
  const costsReady = located.length > 0 && located.every((p) => homes[p.id]?.cost.status !== "loading");
  const onArrived = useCallback(() => setReveal(true), []);
  useEffect(() => {
    if (!reveal || !costsReady || touchedPrice.current) return;
    const id = window.setTimeout(() => {
      if (!touchedPrice.current) setPriceMode("total");
    }, 900);
    return () => window.clearTimeout(id);
  }, [reveal, costsReady]);
  const [moment, setMoment] = useState(false);
  useEffect(() => {
    if (priceMode !== "total" || touchedPrice.current) return;
    setMoment(true);
    const id = window.setTimeout(() => setMoment(false), 6500);
    return () => window.clearTimeout(id);
  }, [priceMode]);

  const choosePrice = (m: PriceMode) => {
    touchedPrice.current = true;
    setMoment(false);
    setPriceMode(m);
  };

  const selected = located.find((p) => p.id === selectedId) ?? null;
  const closeDrawer = useCallback(() => setSelectedId(null), []);

  return (
    <main className={`explore-map${selected ? " has-drawer" : ""}${view === "list" ? " is-list" : ""}`}>
      {properties.status === "ok" && (
        <HavenMap
          pins={pins}
          places={places}
          selectedId={selectedId}
          onSelect={setSelectedId}
          compareIds={compare}
          panel={narrow ? "sheet" : "side"}
          overviewNonce={overviewNonce}
          onArrived={onArrived}
        />
      )}

      <MapControls
        count={shown.length}
        query={query}
        onQuery={setQuery}
        priceMode={priceMode}
        onPriceMode={choosePrice}
        lenses={lenses}
        lens={lens}
        onLens={setLensId}
        budget={budget}
        onBudget={setBudget}
        tally={tally}
        onOverview={() => {
          setSelectedId(null);
          setOverviewNonce((n) => n + 1);
        }}
        view={view}
        onView={setView}
      />

      {properties.status === "loading" && <div className="map-status">Loading homes…</div>}
      {properties.status !== "loading" && properties.status !== "ok" && (
        <div className="map-status">
          <LoadProblem result={properties} onRetry={reload} />
        </div>
      )}

      {moment && (
        <div className="map-moment" role="status">
          <Icon name="spark" size={18} />
          <p>
            <b>That was rent.</b> Now each pin shows Haven’s estimate of the whole month: rent,
            council tax, energy and other bills.
          </p>
          <button type="button" className="text-button" onClick={() => choosePrice("rent")}>
            Show rent
          </button>
        </div>
      )}

      {view === "list" && (
        <section className="map-list" aria-label="Homes as a list">
          {draft.areas.length > 0 && <p className="list-note">Showing {draft.areas.join(", ")} first.</p>}
          <div className="property-grid">
            {shown.map((p) => (
              <PropertyCard key={p.id} property={p} />
            ))}
          </div>
        </section>
      )}

      {selected && view === "map" && (
        <PropertyDrawer
          property={selected}
          home={homes[selected.id]}
          uploads={uploads}
          onUploadsChange={setUploads}
          onClose={closeDrawer}
        />
      )}

      {view === "map" && items && (
        <CompareTray properties={items} homes={homes} lens={lens} stateFor={stateFor} onFocus={setSelectedId} />
      )}
    </main>
  );
}
