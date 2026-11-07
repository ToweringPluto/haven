import { useEnumLabel } from "../api/enums";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { EdinburghSketch } from "../components/EdinburghSketch";
import { Icon } from "../components/Icon";
import { PropertyCard } from "../components/PropertyCard";
import { SignInPrompt } from "../components/SignInPrompt";
import { ACCESS_OPTIONS, DESTINATIONS } from "../data/onboarding";
import { formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

export default function Dashboard() {
  const { go } = useNavigation();
  const label = useEnumLabel();
  const { draft, saved: profile } = useRenterProfile();
  const { saved } = useShortlist();
  const { isConfigured, isAuthenticated, user } = useAuth();
  // Saved comparisons are a signed-in feature; without Auth0 configured the demo shows them.
  const needsSignIn = isConfigured && !isAuthenticated;
  const firstName = user?.name?.split(" ")[0];
  const [properties] = useLoad(saved.length ? "all" : null, api.properties);
  const savedProperties =
    properties.status === "ok" ? properties.data.items.filter((p) => saved.includes(p.id)) : [];

  const preferences = [
    { label: "Monthly budget", value: profile ? `Up to ${formatGBP(draft.budget)}` : "Not set" },
    { label: "Preferred areas", value: draft.areas.join(", ") || "Anywhere in Edinburgh" },
    {
      label: "Access requirements",
      value:
        ACCESS_OPTIONS.filter((o) => o.key !== "none" && draft.access.includes(o.key))
          .map((o) => o.label)
          .join(", ") || "None stated",
    },
    {
      label: "Priorities",
      value: draft.priorities.map((p) => label("priority", p)).join(", ") || "None stated",
    },
    {
      label: "Regular journeys",
      value:
        DESTINATIONS.filter((d) => draft.destinationIds.includes(d.id))
          .map((d) => d.name)
          .join(", ") || "None added",
    },
  ];

  return (
    <main className="dashboard-page shell">
      <div className="dashboard-head">
        <div>
          <span className="section-kicker">
            {firstName ? `Good to see you, ${firstName}` : "Your shortlist"}
          </span>
          <h1>Your home-finding scrapbook</h1>
          <p>The homes you saved and what you told us you need.</p>
        </div>
        <Button onClick={() => go("explore")}>
          <Icon name="search" size={18} /> Explore homes
        </Button>
      </div>

      <div className="scrapbook-note">
        <span>{firstName ? `${firstName}’s shortlist` : "Your shortlist"}</span>
        <p>
          {saved.length === 0
            ? "Nothing saved yet. Save a home and it will appear here."
            : `${saved.length} ${saved.length === 1 ? "home" : "homes"} saved. Compare them side by side, then book viewings.`}
        </p>
        <EdinburghSketch />
      </div>

      <div className="dashboard-grid">
        <section>
          <div className="section-title">
            <h2>Homes I’m keeping an eye on</h2>
            <button type="button" onClick={() => go("compare")}>
              Compare →
            </button>
          </div>
          {needsSignIn ? (
            <SignInPrompt message="Sign in to keep your saved homes and comparisons" />
          ) : savedProperties.length > 0 ? (
            savedProperties.map((p) => <PropertyCard key={p.id} property={p} />)
          ) : (
            <div className="empty-card">
              <Icon name="heart" size={28} />
              <h3>No saved homes yet</h3>
              <p>Save homes to revisit and compare them here.</p>
              <Button onClick={() => go("explore")}>Start exploring</Button>
            </div>
          )}
        </section>

        <aside className="preferences-card">
          <div className="feature-icon">
            <Icon name="user" />
          </div>
          <h2>What I’m looking for</h2>
          {profile?.personaId && <small>Showing the example renter “{profile.label}”.</small>}
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
