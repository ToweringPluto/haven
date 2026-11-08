import type { RentComparison, RentContext } from "../api/types";
import { formatGBP } from "../lib/format";

const COMPARED: Record<RentComparison, string> = {
  below: "below",
  similar: "about the same as",
  above: "above",
};

/** The listing's rent next to local rent statistics and the housing allowance. Context only. */
export function RentContextNote({ context }: { context: RentContext }) {
  const beds = `${context.bedrooms}-bedroom`;
  return (
    <div className="rent-context">
      <h3>How the rent compares</h3>
      <ul>
        <li>
          {context.rent_vs_median ? (
            <>
              The rent is <b>{COMPARED[context.rent_vs_median]}</b> the typical (median){" "}
              {beds} rent in Lothian of <b>{formatGBP(context.median_gbp_pcm)}</b> a month.
            </>
          ) : (
            <>
              The typical (median) {beds} rent in Lothian is{" "}
              <b>{formatGBP(context.median_gbp_pcm)}</b> a month.
            </>
          )}{" "}
          Half of {beds} lets fall between {formatGBP(context.lower_quartile_gbp_pcm)} and{" "}
          {formatGBP(context.upper_quartile_gbp_pcm)}.
        </li>
        {context.lha_monthly_gbp !== null && (
          <li>
            The Local Housing Allowance for a {beds} home is{" "}
            <b>{formatGBP(context.lha_monthly_gbp)}</b> a month
            {context.rent_vs_lha && (
              <>
                , so the rent is <b>{COMPARED[context.rent_vs_lha]}</b> it
              </>
            )}
            . This matters if you might claim help with housing costs.
          </li>
        )}
      </ul>
      <small>
        Source: {context.statistics_source} (year to{" "}
        {new Date(context.statistics_as_of).toLocaleDateString("en-GB")})
        {context.lha_source && <>; {context.lha_source}</>}. {context.caveats.join(" ")}
      </small>
    </div>
  );
}
