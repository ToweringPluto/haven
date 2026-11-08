import { useRef, useState, type ChangeEvent } from "react";
import { useEnumLabel } from "../api/enums";
import { api } from "../api/client";
import type { Upload, UploadKind } from "../api/types";
import { likelihoodStatus } from "../data/screening";
import { Button } from "./Button";
import { Icon } from "./Icon";
import { Status } from "./Status";

const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";
const MAX_BYTES = 15 * 1024 * 1024;

const KINDS: { value: UploadKind; label: string }[] = [
  { value: "photo", label: "Photo" },
  { value: "floor_plan", label: "Floor plan" },
  { value: "document", label: "Document (e.g. lease, EPC)" },
];

/**
 * Photos, floor plans and documents the renter attaches to this home's report. Every upload
 * has a delete control (UI obligation 6); signals are shown with their likelihood label.
 */
export function EvidenceUploads({
  propertyId,
  uploads,
  onChange,
}: {
  propertyId: string;
  uploads: Upload[];
  onChange: (uploads: Upload[]) => void;
}) {
  const label = useEnumLabel();
  const input = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<UploadKind>("photo");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const add = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_BYTES) return setNotice("That file is over 15 MB. Choose a smaller one.");
    setBusy(true);
    setNotice(null);
    const res = await api.uploadFile(kind, file, propertyId);
    setBusy(false);
    if (res.status === "ok") onChange([...uploads, res.data]);
    else setNotice(res.message);
  };

  const remove = async (id: string) => {
    const res = await api.deleteUpload(id);
    if (res.status === "ok" || res.status === "not_found") {
      onChange(uploads.filter((u) => u.id !== id));
    } else setNotice(res.message);
  };

  return (
    <section className="assessment-card evidence-uploads">
      <span className="section-kicker">Your evidence</span>
      <h2>Add photos or documents to your report</h2>
      <p>
        Photos are checked for possible damp, mould or a step at the entrance using Google’s Gemini
        AI service. Documents are read for the rent, council tax band and EPC rating, and compared
        with the listing. Files are stored with location data removed; delete them at any time.
      </p>
      <div className="evidence-controls">
        <label>
          <span>Type</span>
          <select value={kind} onChange={(e) => setKind(e.target.value as UploadKind)}>
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
        <input ref={input} type="file" accept={ACCEPT} hidden onChange={add} />
        <Button secondary onClick={() => input.current?.click()} disabled={busy}>
          <Icon name="spark" size={18} />
          {busy ? "Checking…" : "Choose file"}
        </Button>
      </div>
      {notice && (
        <p className="screen-notice" role="alert">
          {notice}
        </p>
      )}
      {uploads.length > 0 && (
        <ul className="evidence-list">
          {uploads.map((u) => {
            const flagged = u.signals.filter(
              (s) => s.likelihood === "possible" || s.likelihood === "likely",
            );
            const facts = u.extracted_facts.filter((f) => f.evidence.value !== null);
            return (
              <li key={u.id}>
                <div>
                  <b>{u.filename}</b>
                  <small>
                    {KINDS.find((k) => k.value === u.kind)?.label}
                    {u.evidence_quality &&
                      ` · Photo quality: ${label("evidence_quality", u.evidence_quality)}`}
                  </small>
                  {u.kind === "photo" && u.signals.length > 0 && (
                    <div className="evidence-signals">
                      {flagged.length === 0 ? (
                        <small>No possible issues flagged in this photo.</small>
                      ) : (
                        flagged.map((s) => (
                          <Status key={s.id} type={likelihoodStatus(s.likelihood)}>
                            {label("signal_kind", s.kind)}: {label("likelihood", s.likelihood)}
                          </Status>
                        ))
                      )}
                    </div>
                  )}
                  {facts.length > 0 && (
                    <small>
                      Read from the document:{" "}
                      {facts.map((f) => `${f.name.replace(/_/g, " ")} ${f.evidence.value}`).join(", ")}
                    </small>
                  )}
                </div>
                <Button secondary onClick={() => remove(u.id)} aria-label={`Delete ${u.filename}`}>
                  Delete
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
