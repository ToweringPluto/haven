import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Evidence, Property, Upload } from "../api/types";
import { useLoad } from "../api/useLoad";
import { BackLink } from "../components/BackLink";
import { Button } from "../components/Button";
import { CostSummary } from "../components/CostSummary";
import { EvidenceValue } from "../components/Evidence";
import { EvidenceUploads } from "../components/EvidenceUploads";
import { FindingsList } from "../components/FindingsList";
import { Icon } from "../components/Icon";
import { LoadProblem } from "../components/LoadProblem";
import { ProfileBar } from "../components/ProfileBar";
import { useAuth } from "../auth/AuthProvider";
import { listingImage } from "../data/images";
import { displayTitle, factName } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

type Fact = Evidence<string | number | boolean>;

const FACTS = [
  "rent_pcm_gbp",
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

export default function PropertyDetail() {
  const { go, param: propertyId } = useNavigation();
  const { saved: profile, draft } = useRenterProfile();
  const { isSaved, toggleSaved, addToCompare } = useShortlist();
  const { isConfigured, isAuthenticated, login, getAccessToken } = useAuth();
  const profileId = profile?.id ?? null;
  const id = propertyId ?? "";

  const [property, reloadProperty] = useLoad(propertyId, () => api.property(id));
  const [cost] = useLoad(propertyId && `${propertyId}:${profileId}`, () => api.cost(id, profileId));
  const [suitability] = useLoad(propertyId && profileId && `${propertyId}:${profileId}`, () =>
    api.suitability(id, profileId!),
  );
  const [reportError, setReportError] = useState<string | null>(null);
  const [creatingReport, setCreatingReport] = useState(false);
  const [uploads, setUploads] = useState<Upload[]>([]);

  // Signed in: show the files the renter already added to this home (they're on the account).
  useEffect(() => {
    setUploads([]);
    if (!isAuthenticated || !propertyId) return;
    let cancelled = false;
    void (async () => {
      const res = await api.myUploads(propertyId, await getAccessToken());
      if (!cancelled && res.status === "ok") setUploads(res.data.items);
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, propertyId, getAccessToken]);

  if (!propertyId) {
    return (
      <main className="detail-page shell">
        <BackLink to="explore">Back to homes</BackLink>
        <h1>Choose a home</h1>
        <p>Pick a home from the list to see its details.</p>
      </main>
    );
  }
  if (property.status === "loading") {
    return <main className="detail-page shell" aria-busy="true" style={{ minHeight: "60vh" }} />;
  }
  if (property.status !== "ok") {
    return (
      <main className="detail-page shell">
        <BackLink to="explore">Back to homes</BackLink>
        <LoadProblem result={property} onRetry={reloadProperty} />
      </main>
    );
  }

  const p = property.data;
  const saved = isSaved(p.id);

  const createReport = async () => {
    if (!profileId) return;
    setCreatingReport(true);
    setReportError(null);
    const res = await api.createAssessment(
      profileId,
      p.id,
      uploads.filter((u) => u.property_id === p.id).map((u) => u.id),
      await getAccessToken(),
    );
    setCreatingReport(false);
    if (res.status === "ok") go("report", res.data.id);
    else setReportError(res.message);
  };

  return (
    <main className="detail-page shell">
      <BackLink to="explore">Back to homes</BackLink>
      <div className="detail-gallery single">
        <img src={listingImage(p.id, 1400)} alt="" fetchPriority="high" />
      </div>

      <ProfileBar />

      <div className="detail-layout">
        <div className="detail-main">
          <div className="detail-heading">
            <div>
              <span>{p.area ?? "Edinburgh"}</span>
              <h1>{displayTitle(p.title)}</h1>
            </div>
            <div className="detail-price">
              <EvidenceValue evidence={p.rent_pcm_gbp} name="rent_pcm_gbp" />
              <span>rent per month</span>
            </div>
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
              {p.other_recurring_costs.map((c) => (
                <div key={c.label}>
                  <dt>{c.label}</dt>
                  <dd>
                    <EvidenceValue evidence={c.monthly_gbp} name="monthly_gbp" />
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          {cost.status === "ok" && <CostSummary cost={cost.data} />}
          {cost.status !== "ok" && cost.status !== "loading" && <LoadProblem result={cost} />}

          <section className="assessment-card">
            <span className="section-kicker">Checks against your requirements</span>
            <h2>What works, what may not, and what to check</h2>
            {!profileId && (
              <p>
                Create your renter profile, or pick an example renter above, to check this home
                against specific requirements.
              </p>
            )}
            {profileId && suitability.status === "loading" && <p>Checking…</p>}
            {suitability.status === "ok" &&
              (suitability.data.findings.length ? (
                <FindingsList findings={suitability.data.findings} priorities={draft.priorities} />
              ) : (
                <p>No requirement checks apply to this profile.</p>
              ))}
            {profileId && suitability.status !== "ok" && suitability.status !== "loading" && (
              <LoadProblem result={suitability} />
            )}
          </section>

          <EvidenceUploads
            propertyId={p.id}
            uploads={uploads.filter((u) => u.property_id === p.id)}
            onChange={setUploads}
          />

        </div>

        <aside className="sticky-card">
          <span>Interested in this home?</span>
          <Button onClick={() => toggleSaved(p.id)} aria-pressed={saved}>
            <Icon name={saved ? "check" : "heart"} size={18} />
            {saved ? "Saved" : "Save home"}
          </Button>
          <Button
            secondary
            onClick={() => {
              addToCompare(p.id);
              go("compare");
            }}
          >
            Add to comparison
          </Button>
          {isAuthenticated || !isConfigured ? (
            <Button secondary onClick={createReport} disabled={!profileId || creatingReport}>
              {creatingReport ? "Preparing report…" : "Get the full report"}
            </Button>
          ) : (
            <Button secondary onClick={login}>
              Sign in for the full report
            </Button>
          )}
          {!profileId && <small>Reports need a renter profile.</small>}
          {isAuthenticated && <small>Reports are saved to your account.</small>}
          {profileId && uploads.some((u) => u.property_id === p.id) && (
            <small>Your attached files will be included.</small>
          )}
          {reportError && (
            <small className="screen-notice" role="alert">
              {reportError}
            </small>
          )}
          <div className="safe-note">
            <Icon name="shield" />
            <p>
              <b>Rent safely</b>Never transfer money before viewing and verifying the property.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
