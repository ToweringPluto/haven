import { api } from "../api/client";
import type { Evidence, Property } from "../api/types";
import { useLoad } from "../api/useLoad";
import { BackLink } from "../components/BackLink";
import { Button } from "../components/Button";
import { costHeadline } from "../components/CostSummary";
import { BudgetBadge, EvidenceValue } from "../components/Evidence";
import { LoadProblem } from "../components/LoadProblem";
import { ProfileBar } from "../components/ProfileBar";
import { areaImage } from "../data/images";
import { displayTitle, factName } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

type Fact = Evidence<string | number | boolean>;

const ROWS = [
  "rent_pcm_gbp",
  "bedrooms",
  "floor_level",
  "has_lift",
  "entrance_steps",
  "council_tax_band",
  "epc_rating",
  "main_fuel",
] as const satisfies readonly (keyof Property)[];

export default function Compare() {
  const { go } = useNavigation();
  const { compare, toggleCompare } = useShortlist();
  const [properties, reload] = useLoad("all", api.properties);

  const chosen =
    properties.status === "ok"
      ? compare.flatMap((id) => properties.data.items.filter((p) => p.id === id))
      : [];

  return (
    <main className="compare-page shell">
      <BackLink to="explore">Back to homes</BackLink>
      <div className="compare-title">
        <span className="section-kicker">Your shortlist</span>
        <h1>Compare homes, side by side</h1>
        <p>The same facts for each home, with where each one comes from. No scores or rankings.</p>
      </div>
      <ProfileBar />

      {properties.status !== "loading" && properties.status !== "ok" && (
        <LoadProblem result={properties} onRetry={reload} />
      )}
      {properties.status === "ok" && chosen.length === 0 && (
        <div className="empty-card">
          <h3>Nothing to compare yet</h3>
          <p>Tick “Add to compare” on two or more homes.</p>
          <Button onClick={() => go("explore")}>Browse homes</Button>
        </div>
      )}

      {chosen.length > 0 && (
        <div className="compare-scroll">
          <table className="compare-grid">
            <thead>
              <tr>
                <th scope="col">
                  <span className="visually-hidden">Fact</span>
                </th>
                {chosen.map((p) => (
                  <th key={p.id} scope="col">
                    <img src={areaImage(p.area)} alt="" loading="lazy" />
                    <span>{p.area}</span>
                    <b>{displayTitle(p.title)}</b>
                    <button type="button" className="text-button" onClick={() => go("property", p.id)}>
                      View details
                    </button>
                    <button type="button" className="text-button" onClick={() => toggleCompare(p.id)}>
                      Remove
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Estimated total per month</th>
                {chosen.map((p) => (
                  <td key={p.id}>
                    <CostCell propertyId={p.id} />
                  </td>
                ))}
              </tr>
              {ROWS.map((name) => (
                <tr key={name}>
                  <th scope="row">{factName(name)}</th>
                  {chosen.map((p) => (
                    <td key={p.id}>
                      <EvidenceValue evidence={p[name] as Fact} name={name} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

function CostCell({ propertyId }: { propertyId: string }) {
  const { saved } = useRenterProfile();
  const profileId = saved?.id ?? null;
  const [cost] = useLoad(`${propertyId}:${profileId}`, () => api.cost(propertyId, profileId));
  if (cost.status === "loading") return <span>Estimating…</span>;
  if (cost.status !== "ok") return <span>Not available yet</span>;
  return (
    <span className="compare-cost">
      {costHeadline(cost.data) ?? "Insufficient evidence"}
      <BudgetBadge comparison={cost.data.budget_comparison} />
    </span>
  );
}
