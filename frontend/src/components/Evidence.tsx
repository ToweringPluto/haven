import { useEnumLabel } from "../api/enums";
import type { BudgetComparison, Evidence, Outcome } from "../api/types";
import { formatFact } from "../lib/format";
import type { StatusType } from "../types";
import { Status } from "./Status";

interface EvidenceValueProps<T> {
  evidence: Evidence<T>;
  /** Fact name, used to format the value (e.g. "floor_level" → "3rd floor"). */
  name: string;
  /** Override the formatted value. */
  format?: (value: T) => string;
}

/**
 * A value plus where it came from. The origin is always visible; status, source, date and
 * note are one click away (UI obligation 1). Insufficient evidence is shown as such, never
 * as a blank, zero or guess (obligation 5).
 */
export function EvidenceValue<T extends string | number | boolean>({
  evidence,
  name,
  format,
}: EvidenceValueProps<T>) {
  const label = useEnumLabel();
  const insufficient = evidence.value === null || evidence.status === "insufficient";
  const origin = label("origin", evidence.origin);
  const status = label("status", evidence.status);
  const isEstimate = evidence.origin === "estimate" || evidence.status === "estimated";

  const shown = insufficient
    ? label("status", "insufficient")
    : format
      ? format(evidence.value as T)
      : formatFact(name, evidence.value as T, label);

  return (
    <span className="evidence">
      <span className={`evidence-value ${insufficient ? "is-insufficient" : ""}`}>
        {isEstimate && !insufficient && <span className="estimate-prefix">about </span>}
        {shown}
      </span>
      <details className="evidence-info">
        <summary aria-label={`${origin}. Show where this comes from`}>{origin}</summary>
        <dl className="evidence-pop">
          <div>
            <dt>Where from</dt>
            <dd>{origin}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{status}</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>{evidence.source}</dd>
          </div>
          <div>
            <dt>As of</dt>
            <dd>{evidence.as_of ?? "Not dated"}</dd>
          </div>
          {evidence.confidence !== null && (
            <div>
              <dt>Confidence</dt>
              <dd>{Math.round(evidence.confidence * 100)}%</dd>
            </div>
          )}
          {evidence.note && <p>{evidence.note}</p>}
        </dl>
      </details>
    </span>
  );
}

// `unknown` and `concern` look and read differently (obligation 2); none relies on colour
// alone (obligation 7): each has its own symbol and the server's text label.
const OUTCOME_TYPE: Record<string, StatusType> = { meets: "good", concern: "warn", unknown: "info" };
const BUDGET_TYPE: Record<string, StatusType> = { within: "good", over: "warn", unknown: "info" };

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const label = useEnumLabel();
  return <Status type={OUTCOME_TYPE[outcome] ?? "info"}>{label("outcome", outcome)}</Status>;
}

export function BudgetBadge({ comparison }: { comparison: BudgetComparison }) {
  const label = useEnumLabel();
  return (
    <Status type={BUDGET_TYPE[comparison] ?? "info"}>
      {label("budget_comparison", comparison)}
    </Status>
  );
}
