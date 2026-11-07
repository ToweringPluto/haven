import { memo } from "react";
import { formatGBP } from "../lib/format";
import { scoreStatus, type Property } from "../data/properties";
import { useNavigation } from "../state/navigation";
import { useShortlist } from "../state/shortlist";
import { Icon } from "./Icon";
import { Status } from "./Status";

export const PropertyCard = memo(function PropertyCard({ property }: { property: Property }) {
  const { go } = useNavigation();
  const { isSaved, toggleSaved, compare, toggleCompare } = useShortlist();
  const saved = isSaved(property.id);

  return (
    <article className="property-card">
      <div className="property-image">
        <img src={property.image} alt={property.name} loading="lazy" decoding="async" />
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
        <span className={`match-badge ${property.score < 80 ? "medium" : ""}`}>
          {property.score}% match
        </span>
      </div>
      <div className="property-body">
        <small>{property.area}</small>
        <h3>{property.name}</h3>
        <p>{property.details}</p>
        <div className="property-cost">
          <div>
            <b>{formatGBP(property.rent)}</b>
            <span>rent pcm</span>
          </div>
          <div>
            <b>{formatGBP(property.total)}</b>
            <span>est. total pcm</span>
          </div>
        </div>
        <div className="journey-snapshot">
          <Icon name="train" size={18} />
          <span>
            <b>{property.journey}</b>
            <small>{property.transit}</small>
          </span>
        </div>
        <div className="property-status">
          <Status type={scoreStatus(property.score)}>{property.status}</Status>
          <button type="button" onClick={() => go("property")}>
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
