import { memo } from "react";
import { api } from "../api/client";
import type { Property } from "../api/types";
import { useLoad } from "../api/useLoad";
import { areaImage } from "../data/images";
import { displayTitle } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";
import { costHeadline } from "./CostSummary";
import { BudgetBadge, EvidenceValue } from "./Evidence";
import { Icon } from "./Icon";

export const PropertyCard = memo(function PropertyCard({ property }: { property: Property }) {
  const { go } = useNavigation();
  const { saved: profile } = useRenterProfile();
  const { isSaved, toggleSaved, compare, toggleCompare } = useShortlist();
  const saved = isSaved(property.id);
  const profileId = profile?.id ?? null;
  const [cost] = useLoad(`${property.id}:${profileId}`, () => api.cost(property.id, profileId));

  return (
    <article className="property-card">
      <div className="property-image">
        <img src={areaImage(property.area)} alt="" loading="lazy" decoding="async" />
        <span className="area-photo-caption">Area photo, not this property</span>
        <button
          type="button"
          className={saved ? "hearted" : ""}
          aria-label={saved ? "Remove saved property" : "Save property"}
          aria-pressed={saved}
          onClick={() => toggleSaved(property.id)}
        >
          <Icon name="heart" />
          <span className="heart-tooltip">{saved ? "Kept for later" : "Keep this one"}</span>
        </button>
      </div>
      <div className="property-body">
        {property.illustrative && <span className="illustrative-tag">Illustrative — not a real listing</span>}
        <small>{property.area ?? "Edinburgh"}</small>
        <h3>{displayTitle(property.title)}</h3>
        <p className="property-facts">
          <EvidenceValue evidence={property.bedrooms} name="bedrooms" />
          <EvidenceValue evidence={property.floor_level} name="floor_level" />
          <EvidenceValue evidence={property.has_lift} name="has_lift" />
          <EvidenceValue evidence={property.entrance_steps} name="entrance_steps" />
        </p>
        <div className="property-cost">
          <div>
            <EvidenceValue evidence={property.rent_pcm_gbp} name="rent_pcm_gbp" />
            <span>rent pcm</span>
          </div>
          <div aria-live="polite">
            {cost.status === "loading" && <span>Estimating total…</span>}
            {cost.status === "ok" && (
              <>
                <b>{costHeadline(cost.data) ?? "Total: insufficient evidence"}</b>
                <BudgetBadge comparison={cost.data.budget_comparison} />
              </>
            )}
            {cost.status !== "loading" && cost.status !== "ok" && (
              <span>Total cost not available yet</span>
            )}
          </div>
        </div>
        <div className="property-status">
          <button type="button" onClick={() => go("property", property.id)}>
            View details <Icon name="chevron" size={15} />
          </button>
        </div>
        <label className="compare-check">
          <input
            type="checkbox"
            checked={compare.includes(property.id)}
            onChange={() => toggleCompare(property.id)}
          />{" "}
          Add to compare
        </label>
      </div>
    </article>
  );
});
