import { api } from "../api/client";
import type { Report } from "../api/types";
import { useLoad } from "../api/useLoad";
import { BackLink } from "../components/BackLink";
import { CostSummary } from "../components/CostSummary";
import { useEnumLabel } from "../api/enums";
import { FindingsList } from "../components/FindingsList";
import { Icon } from "../components/Icon";
import { LoadProblem } from "../components/LoadProblem";
import { ReadAloudButton } from "../components/ReadAloudButton";
import { Status } from "../components/Status";
import { displayTitle } from "../lib/format";
import { useAuth } from "../auth/AuthProvider";
import { useNavigation } from "../state/navigation";

/** Plain-text version of the report sections, for read-aloud. */
function spokenSummary(report: Report): string {
  return report.sections
    .map((s) => `${s.heading}. ${s.sentences.map((x) => x.text).join(" ") || "Nothing noted."}`)
    .join(" ");
}

export default function ReportPage() {
  const { param: reportId } = useNavigation();
  const label = useEnumLabel();
  const { isLoading, isAuthenticated, getAccessToken } = useAuth();
  // Saved reports need the owner's token, so wait for sign-in to settle before loading.
  const key = reportId && !isLoading ? `${reportId}:${isAuthenticated}` : null;
  const [report, reload] = useLoad(key, async () =>
    api.report(reportId ?? "", await getAccessToken()),
  );

  if (report.status === "loading") {
    return <main className="report-page shell" aria-busy="true" style={{ minHeight: "60vh" }} />;
  }
  if (report.status !== "ok") {
    return (
      <main className="report-page shell">
        <BackLink to="explore">Back to homes</BackLink>
        <LoadProblem result={report} onRetry={reload} />
      </main>
    );
  }

  const r = report.data;
  const citeTitle = (id: string) =>
    r.findings.find((f) => f.id === id)?.title ??
    r.signals.find((s) => s.id === id)?.kind.replace(/_/g, " ") ??
    id;

  return (
    <main className="report-page shell">
      <BackLink to="explore">Back to homes</BackLink>

      {/* Always rendered, verbatim (UI obligation 4). */}
      <div className="report-disclaimer" role="note">
        <Icon name="info" />
        <p>{r.disclaimer}</p>
      </div>

      <header className="report-header">
        <span className="section-kicker">Property suitability report</span>
        <h1>{displayTitle(r.property.title)}</h1>
        <p>
          For <b>{r.profile.label}</b> · {new Date(r.created_at).toLocaleDateString("en-GB")}
        </p>
        <ReadAloudButton text={spokenSummary(r)} sampleFile="report-sample.wav" />
      </header>

      <section className="report-sections">
        {r.sections.map((section) => (
          <article key={section.heading} className="report-section">
            <h2>{section.heading}</h2>
            {section.sentences.length === 0 ? (
              <p className="empty-section">Nothing noted here.</p>
            ) : (
              <ul>
                {section.sentences.map((sentence) => (
                  <li key={sentence.text}>
                    {sentence.text}
                    {sentence.cites.length > 0 && (
                      <span className="cites">
                        {" "}
                        Based on:{" "}
                        {sentence.cites.map((id, i) => (
                          <span key={id}>
                            {i > 0 && ", "}
                            <a href={`#finding-${id}`} onClick={(e) => jumpTo(e, id)}>
                              {citeTitle(id)}
                            </a>
                          </span>
                        ))}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </section>

      {r.cost && <CostSummary cost={r.cost} />}

      {r.findings.length > 0 && (
        <section className="assessment-card">
          <span className="section-kicker">The checks behind this report</span>
          <h2>Requirement checks</h2>
          <FindingsList findings={r.findings} priorities={r.profile.priorities} />
        </section>
      )}

      {r.signals.length > 0 && (
        <section className="assessment-card">
          <span className="section-kicker">From uploaded evidence</span>
          <h2>Possible issues to inspect</h2>
          <ul className="findings">
            {r.signals.map((s) => (
              <li key={s.id} id={`finding-${s.id}`} className="finding">
                <Status type={s.likelihood === "insufficient_evidence" ? "info" : "warn"}>
                  {label("likelihood", s.likelihood)}
                </Status>
                <h3>{label("signal_kind", s.kind)}</h3>
                {s.note && <p>{s.note}</p>}
                <small>
                  Photo quality: {label("evidence_quality", s.evidence_quality)}
                  {s.confidence !== null && ` · Confidence ${Math.round(s.confidence * 100)}%`}
                </small>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

/** In-page jump without changing the hash route. */
function jumpTo(event: React.MouseEvent, id: string) {
  event.preventDefault();
  document.getElementById(`finding-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}
