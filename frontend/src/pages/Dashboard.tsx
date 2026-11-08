import { useEffect, useState } from "react";
import { useEnumLabel } from "../api/enums";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { useAuth } from "../auth/AuthProvider";
import { AccessibilitySettings } from "../components/AccessibilitySettings";
import { Button } from "../components/Button";
import { EdinburghSketch } from "../components/EdinburghSketch";
import { Icon } from "../components/Icon";
import { PropertyCard } from "../components/PropertyCard";
import { SignInPrompt } from "../components/SignInPrompt";
import { ACCESS_OPTIONS, DESTINATIONS } from "../data/onboarding";
import { displayTitle, formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { useShortlist } from "../state/shortlist";

export default function Dashboard() {
  const { go, param } = useNavigation();
  const label = useEnumLabel();
  const { draft, saved: profile, deleteProfile, reset: resetProfile } = useRenterProfile();
  const { saved, syncError, reset: resetShortlist } = useShortlist();
  const { isConfigured, isAuthenticated, user, getAccessToken } = useAuth();
  const firstName = user?.name?.split(" ")[0];
  const [reports, reloadReports] = useLoad(isAuthenticated ? "my-reports" : null, async () =>
    api.myReports(await getAccessToken()),
  );
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // `#/dashboard/accessibility` (the nav button) jumps straight to the settings.
  useEffect(() => {
    if (param !== "accessibility") return;
    const section = document.getElementById("accessibility");
    section?.scrollIntoView({ block: "start" });
    section?.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
  }, [param]);

  const removeProfile = async () => {
    if (!window.confirm("Delete your saved renter profile? Your reports keep their own copy.")) {
      return;
    }
    setBusy(true);
    const problem = await deleteProfile();
    setBusy(false);
    setNotice(problem ?? "Your profile was deleted.");
  };

  const deleteEverything = async () => {
    const ok = window.confirm(
      "Delete everything Haven has saved for you: your profile, reports, uploaded files and " +
        "saved homes? This can’t be undone.",
    );
    if (!ok) return;
    setBusy(true);
    const res = await api.deleteMyData(await getAccessToken());
    setBusy(false);
    if (res.status !== "ok") return setNotice(`Nothing was deleted: ${res.message}`);
    resetProfile();
    resetShortlist();
    reloadReports();
    const d = res.data;
    setNotice(
      `Deleted ${d.profiles} ${d.profiles === 1 ? "profile" : "profiles"}, ${d.reports} ` +
        `${d.reports === 1 ? "report" : "reports"}, ${d.uploads} ` +
        `${d.uploads === 1 ? "upload" : "uploads"}${d.saved_homes ? " and your saved homes" : ""}.`,
    );
  };
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
          {isConfigured && !isAuthenticated && (
            <SignInPrompt message="Sign in to keep your saved homes on every device" />
          )}
          {syncError && (
            <p className="screen-notice" role="alert">
              {syncError}
            </p>
          )}
          {savedProperties.length > 0 ? (
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
          {profile?.owned && (
            <button type="button" className="text-button" onClick={removeProfile} disabled={busy}>
              Delete my profile
            </button>
          )}
        </aside>
      </div>

      {isAuthenticated && (
        <div className="dashboard-grid account-grid">
          <section>
            <div className="section-title">
              <h2>My reports</h2>
            </div>
            {reports.status === "loading" && <p>Loading your reports…</p>}
            {reports.status === "ok" && reports.data.items.length === 0 && (
              <p>No reports yet. Open a home and choose “Get the full report”.</p>
            )}
            {reports.status === "ok" && reports.data.items.length > 0 && (
              <ul className="report-list">
                {reports.data.items.map((r) => (
                  <li key={r.id}>
                    <button type="button" onClick={() => go("report", r.id)}>
                      <b>{displayTitle(r.property_title)}</b>
                      <small>
                        For {r.profile_label} ·{" "}
                        {new Date(r.created_at).toLocaleDateString("en-GB")}
                      </small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {reports.status !== "loading" && reports.status !== "ok" && (
              <p className="screen-notice">{reports.message}</p>
            )}
          </section>

          <aside className="preferences-card privacy-card">
            <div className="feature-icon">
              <Icon name="shield" />
            </div>
            <h2>Your data</h2>
            <p>
              Haven saves your renter profile (including any access needs), your reports, the files
              you upload and your saved homes to your account. Only you can see them.
            </p>
            <Button secondary onClick={deleteEverything} disabled={busy}>
              {busy ? "Deleting…" : "Delete all my data"}
            </Button>
          </aside>
        </div>
      )}
      <AccessibilitySettings />

      {notice && (
        <p className="screen-notice" role="status">
          {notice}
        </p>
      )}
    </main>
  );
}
