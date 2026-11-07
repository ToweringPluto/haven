import type { Finding, Priority } from "../api/types";
import { factName } from "../lib/format";
import { EvidenceValue, OutcomeBadge } from "./Evidence";

// Which findings each renter priority relates to. Findings are ordered by the renter's own
// priorities (allowed by obligation 3); they are never summed, counted or scored.
const PRIORITY_MATCHERS: Record<string, (f: Finding) => boolean> = {
  total_cost: (f) => f.category === "cost",
  heating_cost: (f) => f.category === "cost",
  step_free_access: (f) => f.rule_id.includes("step_free"),
  lift_access: (f) => f.rule_id.includes("lift"),
  transport_access: (f) => f.rule_id.includes("stop") || f.category === "location",
  travel_time: (f) => f.rule_id.includes("travel") || f.category === "location",
};

function priorityRank(finding: Finding, priorities: Priority[]): number {
  const index = priorities.findIndex((p) => PRIORITY_MATCHERS[p]?.(finding));
  return index === -1 ? priorities.length : index;
}

export function FindingsList({
  findings,
  priorities,
}: {
  findings: Finding[];
  priorities: Priority[];
}) {
  const ordered = [...findings].sort(
    (a, b) => priorityRank(a, priorities) - priorityRank(b, priorities),
  );

  return (
    <ul className="findings">
      {ordered.map((finding) => (
        <li key={finding.id} id={`finding-${finding.id}`} className={`finding is-${finding.outcome}`}>
          <OutcomeBadge outcome={finding.outcome} />
          <h3>{finding.title}</h3>
          <p>{finding.reason}</p>
          {finding.next_step && finding.outcome !== "meets" && (
            <p className="next-step">
              <b>Check before signing:</b> {finding.next_step}
            </p>
          )}
          {finding.facts.length > 0 && (
            <div className="finding-facts">
              {finding.facts.map((fact) => (
                <span key={fact.name}>
                  {factName(fact.name)}: <EvidenceValue evidence={fact.evidence} name={fact.name} />
                </span>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
