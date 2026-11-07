import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { PropertyCard } from "../components/PropertyCard";
import { IMAGES } from "../data/images";
import { PROPERTIES } from "../data/properties";
import { formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

export default function Explore() {
  const { go } = useNavigation();
  const { profile } = useRenterProfile();
  const { compare, clearCompare } = useShortlist();

  return (
    <main className="explore-page shell">
      <div className="explore-title">
        <div>
          <span className="section-kicker">Personalised for you</span>
          <h1>Homes that fit your life</h1>
          <p>Here are 18 places that look promising. Kettle on—let’s take a proper look.</p>
        </div>
        <button type="button" className="profile-chip" onClick={() => go("onboarding")}>
          <Icon name="user" size={17} /> Edit renter profile
        </button>
      </div>

      <section className="neighbourhood-opening">
        <div className="neighbourhood-opening-photo">
          <img src={IMAGES.leith} alt="Traditional homes in Leith" decoding="async" />
          <span>Today’s neighbourhood note</span>
        </div>
        <div>
          <span className="section-kicker">A closer look at Leith</span>
          <h2>Creative, well connected, and never short of a good coffee.</h2>
          <p>
            The Shore is lively at weekends, while the streets towards Pilrig feel calmer. The tram
            makes town easy, and the Water of Leith gives you a proper Sunday walk.
          </p>
          <div className="local-details">
            <span>
              <Icon name="train" size={16} /> 14 min by tram to Princes Street
            </span>
            <span>
              <Icon name="leaf" size={16} /> 6 green spaces nearby
            </span>
          </div>
        </div>
        <div className="map-doodle" aria-hidden="true">
          <Icon name="map" size={26} />
          <span className="map-route" />
          <b>The Shore</b>
          <small>Leith Walk</small>
        </div>
      </section>

      <div className="search-row">
        <form className="search-box" role="search" onSubmit={(e) => e.preventDefault()}>
          <Icon name="search" />
          <input aria-label="Search areas" placeholder="Search area or postcode" />
          <button type="submit">Search</button>
        </form>
        <button type="button" className="filter-button">
          Filters <span>3</span>
        </button>
        <div className="view-toggle">
          <button type="button" className="active" aria-pressed="true">
            ☷ List
          </button>
          <button type="button" aria-pressed="false">
            <Icon name="map" size={16} /> Map
          </button>
        </div>
      </div>

      <div className="active-filters">
        <span>Up to {formatGBP(profile.budget)} ×</span>
        <span>Step-free preferred ×</span>
        <span>≤ 35 min commute ×</span>
        <button type="button">Clear all</button>
      </div>

      <div className="property-grid">
        {PROPERTIES.map((p) => (
          <PropertyCard key={p.id} property={p} />
        ))}
      </div>

      {compare.length > 0 && (
        <div className="compare-bar">
          <span>
            <b>{compare.length}</b> {compare.length === 1 ? "property" : "properties"} selected
          </span>
          <div>
            <button type="button" onClick={clearCompare}>
              Clear
            </button>
            <Button
              onClick={() => go("compare")}
              className={compare.length < 2 ? "disabled" : ""}
              disabled={compare.length < 2}
            >
              Compare properties <Icon name="arrow" />
            </Button>
          </div>
        </div>
      )}
    </main>
  );
}
