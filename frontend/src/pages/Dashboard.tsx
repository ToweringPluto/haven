import { Button } from "../components/Button";
import { EdinburghSketch } from "../components/EdinburghSketch";
import { Icon } from "../components/Icon";
import { PropertyCard } from "../components/PropertyCard";
import { NO_ACCESS_NEEDS } from "../data/onboarding";
import { getProperty } from "../data/properties";
import { formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile, type RenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

function keyPriority({ access, priorities }: RenterProfile) {
  return access.find((a) => a !== NO_ACCESS_NEEDS) ?? priorities[0] ?? "Not set yet";
}

function dailyJourney({ destinations }: RenterProfile) {
  if (destinations.length === 0) return "Not added";
  const more = destinations.length - 1;
  return more > 0 ? `${destinations[0]} +${more} more` : destinations[0];
}

export default function Dashboard() {
  const { go } = useNavigation();
  const { profile } = useRenterProfile();
  const { saved } = useShortlist();
  const savedProperties = saved.flatMap((id) => getProperty(id) ?? []);

  const preferences = [
    { label: "Monthly rent", value: `Up to ${formatGBP(profile.budget)}` },
    { label: "Preferred areas", value: profile.areas.join(", ") || "Anywhere in Edinburgh" },
    { label: "Key priority", value: keyPriority(profile) },
    { label: "Daily journey", value: dailyJourney(profile) },
  ];

  return (
    <main className="dashboard-page shell">
      <div className="dashboard-head">
        <div>
          <span className="section-kicker">Good afternoon, Anna</span>
          <h1>Your home-finding scrapbook</h1>
          <p>
            A quiet corner for the places you liked, the notes you made and the journeys you
            checked.
          </p>
        </div>
        <Button onClick={() => go("explore")}>
          <Icon name="search" size={18} /> Explore homes
        </Button>
      </div>

      <div className="scrapbook-note">
        <span>Anna’s shortlist</span>
        <p>
          {savedProperties.length === 0
            ? "Nothing pinned here yet. Save a home and we’ll keep your notes together."
            : savedProperties.length === 1
              ? "One promising place saved. Next up: check the entrance and book a viewing."
              : `${savedProperties.length} promising places saved. Compare them side by side, then book viewings.`}
        </p>
        <EdinburghSketch />
      </div>

      <div className="dashboard-grid">
        <section>
          <div className="section-title">
            <h2>Homes I’m keeping an eye on</h2>
            <button type="button" onClick={() => go("explore")}>
              View all →
            </button>
          </div>
          {savedProperties.length > 0 ? (
            savedProperties.map((p) => <PropertyCard key={p.id} property={p} />)
          ) : (
            <div className="empty-card">
              <Icon name="heart" size={28} />
              <h3>No saved homes yet</h3>
              <p>Save properties to revisit and compare them here.</p>
              <Button onClick={() => go("explore")}>Start exploring</Button>
            </div>
          )}
        </section>

        <aside className="preferences-card">
          <div className="feature-icon">
            <Icon name="user" />
          </div>
          <h2>What I’m looking for</h2>
          {preferences.map((pref) => (
            <div key={pref.label}>
              <span>{pref.label}</span>
              <b>{pref.value}</b>
            </div>
          ))}
          <Button secondary onClick={() => go("onboarding")}>
            Edit preferences
          </Button>
        </aside>
      </div>
    </main>
  );
}
