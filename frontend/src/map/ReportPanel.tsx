import { api } from "../api/client";
import type { Report } from "../api/types";
import { useLoad } from "../api/useLoad";
import { useAuth } from "../auth/AuthProvider";
import { Icon } from "../components/Icon";
import { LoadProblem } from "../components/LoadProblem";
import { ReadAloudButton } from "../components/ReadAloudButton";
import { useNavigation } from "../state/navigation";

/** Plain-text version of the report sections, for read-aloud (same wording as the report page). */
function spokenSummary(report: Report): string {
  return report.sections
    .map((s) => `${s.heading}. ${s.sentences.map((x) => x.text).join(" ") || "Nothing noted."}`)
    .join(" ");
}

/** The generated report, revealed section by section inside the drawer. */
export function ReportPanel({ reportId }: { reportId: string }) {
  const { go } = useNavigation();
  const { isLoading, isAuthenticated, getAccessToken } = useAuth();
  // Saved reports need the owner's token, so wait for sign-in to settle before loading.
  const key = !isLoading ? `${reportId}:${isAuthenticated}` : null;
  const [report, reload] = useLoad(key, async () => api.report(reportId, await getAccessToken()));

  if (report.status === "loading") return <div className="drawer-skeleton" aria-busy="true">Opening the report…</div>;
  if (report.status !== "ok") return <LoadProblem result={report} onRetry={reload} />;

  const r = report.data;
  const citeTitle = (id: string) =>
    r.findings.find((f) => f.id === id)?.title ?? r.signals.find((s) => s.id === id)?.kind.replace(/_/g, " ") ?? id;

  return (
    <div className="report-panel">
      {/* Always shown, verbatim. */}
      <div className="report-disclaimer" role="note">
        <Icon name="info" />
        <p>{r.disclaimer}</p>
      </div>
      {r.illustrative && <span className="illustrative-tag">Illustrative report built from example data</span>}
      <div className="report-panel-tools">
        <ReadAloudButton text={spokenSummary(r)} sampleFile="report-sample.wav" />
        <button type="button" className="text-button" onClick={() => go("report", r.id)}>
          Open full report <Icon name="arrow" size={15} />
        </button>
      </div>
      {r.sections.map((section, i) => (
        <article key={section.heading} className="report-panel-section" style={{ animationDelay: `${i * 140}ms` }}>
          <h3>{section.heading}</h3>
          {section.sentences.length === 0 ? (
            <p className="empty-section">Nothing noted here.</p>
          ) : (
            <ul>
              {section.sentences.map((s) => (
                <li key={s.text}>
                  {s.text}
                  {s.cites.length > 0 && <small> Based on: {s.cites.map(citeTitle).join(", ")}</small>}
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </div>
  );
}
