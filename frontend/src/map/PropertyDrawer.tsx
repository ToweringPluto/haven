import { useEffect, useState } from "react";
import type { CostBreakdown, Evidence, Property, Upload } from "../api/types";
import { useCreateReport } from "../api/useCreateReport";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { CostSummary } from "../components/CostSummary";
import { EvidenceValue } from "../components/Evidence";
import { EvidenceUploads } from "../components/EvidenceUploads";
import { FindingsList } from "../components/FindingsList";
import { Icon } from "../components/Icon";
import { LoadProblem } from "../components/LoadProblem";
import { listingImage } from "../data/images";
import { displayTitle, factName, formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";
import { MAX_COMPARE } from "./CompareTray";
import { ReportPanel } from "./ReportPanel";
import type { HomeData } from "./useMapData";

type Fact = Evidence<string | number | boolean>;

const FACTS = [
  "bedrooms",
  "property_type",
  "floor_area_m2",
  "floor_level",
  "has_lift",
  "entrance_steps",
  "council_tax_band",
  "epc_rating",
  "main_fuel",
] as const satisfies readonly (keyof Property)[];

interface PropertyDrawerProps {
  property: Property;
  home: HomeData | undefined;
  uploads: Upload[];
  onUploadsChange: (uploads: Upload[]) => void;
  onClose: () => void;
}

/** Everything Haven knows about one home, opened over the map. */
export function PropertyDrawer({ property: p, home, uploads, onUploadsChange, onClose }: PropertyDrawerProps) {
  const { go } = useNavigation();
  const { saved: profile, draft } = useRenterProfile();
  const { isSaved, toggleSaved, compare, toggleCompare } = useShortlist();
  const { isConfigured, isAuthenticated, login } = useAuth();
  const { create, creating, error } = useCreateReport();
  const [reportId, setReportId] = useState<string | null>(null);
  const profileId = profile?.id ?? null;
  const saved = isSaved(p.id);
  const comparing = compare.includes(p.id);
  const compareFull = !comparing && compare.length >= MAX_COMPARE;
  const mine = uploads.filter((u) => u.property_id === p.id);

  // A new home (or renter) starts without a report.
  useEffect(() => setReportId(null), [p.id, profileId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const cost = home?.cost;
  const suitability = home?.suitability;

  return (
    <aside className="map-drawer" aria-label={`Details: ${displayTitle(p.title)}`} key={p.id}>
      <div className="drawer-hero">
        <img src={listingImage(p.id)} alt="" />
        <button type="button" className="drawer-close" onClick={onClose} aria-label="Close details">
          <Icon name="x" size={18} />
        </button>
      </div>

      <div className="drawer-body">
        <header className="drawer-heading">
          <span className="drawer-area">{p.area ?? "Edinburgh"}</span>
          <h2>{displayTitle(p.title)}</h2>
          <div className="drawer-prices">
            <div>
              <EvidenceValue evidence={p.rent_pcm_gbp} name="rent_pcm_gbp" format={formatGBP} />
              <small>rent a month</small>
            </div>
            {cost?.status === "ok" && cost.data.total_monthly_gbp.value !== null && (
              <div className="drawer-total">
                <b>{formatGBP(cost.data.total_monthly_gbp.value)}</b>
                <small>estimated true monthly cost</small>
              </div>
            )}
          </div>
        </header>

        <div className="drawer-actions">
          <Button onClick={() => toggleSaved(p.id)} aria-pressed={saved}>
            <Icon name={saved ? "check" : "heart"} size={17} />
            {saved ? "Saved" : "Save"}
          </Button>
          <Button secondary onClick={() => toggleCompare(p.id)} aria-pressed={comparing} disabled={compareFull}>
            <Icon name={comparing ? "check" : "plus"} size={17} />
            {comparing ? "Comparing" : compareFull ? `Compare is full (${MAX_COMPARE})` : "Compare"}
          </Button>
          <button type="button" className="text-button" onClick={() => go("property", p.id)}>
            Full page <Icon name="arrow" size={15} />
          </button>
        </div>

        {cost?.status === "ok" && <CostBar cost={cost.data} />}
        {cost?.status === "ok" && <CostSummary cost={cost.data} />}
        {cost?.status === "loading" && <div className="drawer-skeleton" aria-busy="true">Estimating the true cost…</div>}
        {cost && cost.status !== "ok" && cost.status !== "loading" && <LoadProblem result={cost} />}

        <section className="assessment-card">
          <span className="section-kicker">Checks against your requirements</span>
          {!profileId && (
            <p>Pick an example renter or create your profile (top left) to check this home against specific needs.</p>
          )}
          {suitability?.status === "loading" && <p>Checking…</p>}
          {suitability?.status === "ok" &&
            (suitability.data.findings.length ? (
              <FindingsList findings={suitability.data.findings} priorities={draft.priorities} />
            ) : (
              <p>No requirement checks apply to this profile.</p>
            ))}
          {suitability && suitability.status !== "ok" && suitability.status !== "loading" && (
            <LoadProblem result={suitability} />
          )}
        </section>

        <EvidenceUploads propertyId={p.id} uploads={mine} onChange={onUploadsChange} />

        <section className="drawer-screening">
          <Icon name="spark" />
          <div>
            <b>Screen a listing photo</b>
            <p>Look for possible issues worth asking about, such as entrance steps or signs of damp.</p>
          </div>
          <Button secondary onClick={() => go("screening", p.id)}>
            Start <Icon name="arrow" size={15} />
          </Button>
        </section>

        <section className="drawer-report">
          <span className="section-kicker">Report</span>
          {reportId ? (
            <ReportPanel reportId={reportId} />
          ) : (
            <>
              <p>
                A plain-language summary of the cost, the checks and anything you uploaded, built only
                from the results above.
                {mine.length > 0 && " Your attached files will be included."}
              </p>
              {isAuthenticated || !isConfigured ? (
                <Button
                  onClick={async () => profileId && setReportId(await create(profileId, p.id, uploads))}
                  disabled={!profileId || creating}
                >
                  <Icon name="spark" size={17} />
                  {creating ? "Preparing report…" : "Generate report"}
                </Button>
              ) : (
                <Button onClick={login}>Sign in for the report</Button>
              )}
              {!profileId && <small>Reports need a renter profile.</small>}
              {error && (
                <small className="screen-notice" role="alert">
                  {error}
                </small>
              )}
            </>
          )}
        </section>

        <div className="safe-note">
          <Icon name="shield" />
          <p>
            <b>Rent safely</b>Never transfer money before viewing and verifying the property.
          </p>
        </div>

        <section className="facts-card">
          <span className="section-kicker">What we know about this home</span>
          <dl className="facts-grid">
            {FACTS.map((name) => (
              <div key={name}>
                <dt>{factName(name)}</dt>
                <dd>
                  <EvidenceValue evidence={p[name] as Fact} name={name} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </aside>
  );
}

const SEGMENT_COLOURS = ["var(--teal)", "var(--terracotta)", "var(--sage)", "var(--charcoal)", "var(--line)"];

/** Where the money goes: each estimated line as a share of the month, growing in on open. */
function CostBar({ cost }: { cost: CostBreakdown }) {
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const lines = cost.lines.filter((l) => (l.monthly_gbp.value ?? 0) > 0);
  const total = lines.reduce((sum, l) => sum + (l.monthly_gbp.value ?? 0), 0);
  if (total <= 0) return null;
  const missing = cost.lines.length - lines.length;
  return (
    <figure className="cost-bar">
      <figcaption className="section-kicker">Where the month goes · estimate</figcaption>
      <div className="cost-bar-track" role="img" aria-label={lines.map((l) => `${l.label} ${formatGBP(l.monthly_gbp.value ?? 0)}`).join(", ")}>
        {lines.map((l, i) => (
          <span
            key={`${l.kind}-${l.label}`}
            style={{
              width: grown ? `${((l.monthly_gbp.value ?? 0) / total) * 100}%` : "0%",
              background: SEGMENT_COLOURS[i % SEGMENT_COLOURS.length],
              transitionDelay: `${i * 90}ms`,
            }}
          />
        ))}
      </div>
      <ul className="cost-bar-legend">
        {lines.map((l, i) => (
          <li key={`${l.kind}-${l.label}`}>
            <i style={{ background: SEGMENT_COLOURS[i % SEGMENT_COLOURS.length] }} />
            {l.label} <b>{formatGBP(l.monthly_gbp.value ?? 0)}</b>
          </li>
        ))}
      </ul>
      {missing > 0 && (
        <small>
          {missing} {missing === 1 ? "line has" : "lines have"} too little information to estimate and
          {missing === 1 ? " isn’t" : " aren’t"} shown here.
        </small>
      )}
    </figure>
  );
}
