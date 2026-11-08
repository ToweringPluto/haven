import type { CostBreakdown } from "../api/types";
import { formatGBP } from "../lib/format";
import { BudgetBadge, EvidenceValue } from "./Evidence";
import { Icon } from "./Icon";
import { RentContextNote } from "./RentContextNote";

/** "about £1,495 a month, likely between £1,468 and £1,531", or the insufficient wording. */
export function costHeadline(cost: CostBreakdown): string | null {
  const total = cost.total_monthly_gbp.value;
  if (total === null) return null;
  const range =
    cost.total_low_gbp !== null && cost.total_high_gbp !== null
      ? `, likely between ${formatGBP(cost.total_low_gbp)} and ${formatGBP(cost.total_high_gbp)}`
      : "";
  return `About ${formatGBP(total)} a month${range}`;
}

/** The true monthly cost: every line with its provenance, the range, and the budget check. */
export function CostSummary({ cost }: { cost: CostBreakdown }) {
  const headline = costHeadline(cost);
  return (
    <section className="cost-card">
      <div className="section-title">
        <div>
          <span className="section-kicker">True monthly cost · estimate</span>
          <h2>{headline ?? "Not enough information for a total"}</h2>
        </div>
        <BudgetBadge comparison={cost.budget_comparison} />
      </div>
      <div className="cost-lines">
        {cost.lines.map((line) => (
          <div key={`${line.kind}-${line.label}`}>
            <span>{line.label}</span>
            <span className="cost-line-value">
              <EvidenceValue evidence={line.monthly_gbp} name="monthly_gbp" format={formatGBP} />
              {line.low_gbp !== null && line.high_gbp !== null && (
                <small>
                  {formatGBP(line.low_gbp)}–{formatGBP(line.high_gbp)}
                </small>
              )}
            </span>
          </div>
        ))}
        <div className="cost-total-line">
          <span>
            <b>Estimated total</b>
            {cost.budget_monthly_gbp !== null && (
              <small> · your budget {formatGBP(cost.budget_monthly_gbp)}</small>
            )}
          </span>
          <EvidenceValue evidence={cost.total_monthly_gbp} name="total_gbp" format={formatGBP} />
        </div>
      </div>
      {cost.rent_context && <RentContextNote context={cost.rent_context} />}
      <p>
        <Icon name="info" size={17} /> Estimates, not quotes. A line without enough information is
        marked as such and isn’t counted as £0. Open any source label to see where a figure comes
        from.
      </p>
    </section>
  );
}
