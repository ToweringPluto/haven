import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useEnumLabel } from "../api/enums";
import { api } from "../api/client";
import type { Upload, UploadKind } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { ACCEPTED_IMAGE_TYPES, likelihoodStatus } from "../data/screening";
import { Button } from "./Button";
import { Icon } from "./Icon";
import { Status } from "./Status";

const ACCEPT_ANY = "image/jpeg,image/png,image/webp,application/pdf";
const MAX_BYTES = 15 * 1024 * 1024;

const KINDS: { value: UploadKind; label: string }[] = [
  { value: "photo", label: "Photo" },
  { value: "floor_plan", label: "Floor plan" },
  { value: "document", label: "Document (e.g. lease, EPC)" },
];

/**
 * Photos, floor plans and documents the renter attaches to this home's report. Photos get the
 * AI check (possible damp, mould, entrance step). Uploads are saved to the signed-in renter's
 * account, so they come back after a reload. Every upload has a delete control (UI obligation 6);
 * signals are shown with their likelihood label.
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
  const { isConfigured, isAuthenticated, isLoading, login, getAccessToken } = useAuth();
  const photoInput = useRef<HTMLInputElement>(null);
  const otherInput = useRef<HTMLInputElement>(null);
  const [otherKind, setOtherKind] = useState<UploadKind>("document");
  const [busy, setBusy] = useState<UploadKind | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Previews of photos chosen in this visit (the server doesn't send files back).
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const previewUrls = useRef<string[]>([]);

  useEffect(() => () => previewUrls.current.forEach((url) => URL.revokeObjectURL(url)), []);

  const add = async (kind: UploadKind, event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_BYTES) return setNotice("That file is over 15 MB. Choose a smaller one.");
    setBusy(kind);
    setNotice(null);
    const res = await api.uploadFile(kind, file, propertyId, await getAccessToken());
    setBusy(null);
    if (res.status !== "ok") return setNotice(res.message);
    if (file.type.startsWith("image/")) {
      const url = URL.createObjectURL(file);
      previewUrls.current.push(url);
      setPreviews((p) => ({ ...p, [res.data.id]: url }));
    }
    onChange([...uploads, res.data]);
  };

  const remove = async (id: string) => {
    const res = await api.deleteUpload(id, await getAccessToken());
    if (res.status === "ok" || res.status === "not_found") {
      onChange(uploads.filter((u) => u.id !== id));
    } else setNotice(res.message);
  };

  return (
    <section className="assessment-card evidence-uploads">
      <div className="evidence-head">
        <div className="feature-icon">
          <Icon name="spark" />
        </div>
        <div>
          <span className="section-kicker">AI photo check</span>
          <h2>Look closer before you view</h2>
        </div>
      </div>
      <p>
        Upload a photo from the listing or your viewing. Google’s Gemini AI looks for possible damp,
        mould or a step at the entrance: things worth asking about, never a diagnosis. You can also
        add documents (we read the rent, council tax band and EPC rating and compare them with the
        listing). Files are stored with location data removed; delete them at any time.
      </p>

      {!isAuthenticated ? (
        <div className="evidence-signin">
          <Icon name="user" size={18} />
          {isConfigured ? (
            <>
              <span>Sign in to upload photos. They’re saved to your account and added to your report.</span>
              <Button onClick={login} disabled={isLoading}>
                <Icon name="upload" size={18} /> Sign in to upload a photo
              </Button>
            </>
          ) : (
            <span>Uploading needs sign-in, which isn’t set up on this copy of Haven.</span>
          )}
        </div>
      ) : (
        <div className="evidence-controls">
          <input
            ref={photoInput}
            type="file"
            accept={ACCEPTED_IMAGE_TYPES.join(",")}
            hidden
            onChange={(e) => add("photo", e)}
          />
          <Button onClick={() => photoInput.current?.click()} disabled={busy !== null}>
            <Icon name="upload" size={18} />
            {busy === "photo" ? "Checking photo…" : "Upload a photo for the AI check"}
          </Button>
          <span className="evidence-or">or add</span>
          <label>
            <span className="visually-hidden">File type</span>
            <select value={otherKind} onChange={(e) => setOtherKind(e.target.value as UploadKind)}>
              {KINDS.filter((k) => k.value !== "photo").map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </label>
          <input
            ref={otherInput}
            type="file"
            accept={ACCEPT_ANY}
            hidden
            onChange={(e) => add(otherKind, e)}
          />
          <Button secondary onClick={() => otherInput.current?.click()} disabled={busy !== null}>
            {busy && busy !== "photo" ? "Reading…" : "Choose file"}
          </Button>
        </div>
      )}
      {notice && (
        <p className="screen-notice" role="alert">
          {notice}
        </p>
      )}
      {uploads.length > 0 && (
        <ul className="evidence-list" aria-live="polite">
          {uploads.map((u) => {
            const flagged = u.signals.filter(
              (s) => s.likelihood === "possible" || s.likelihood === "likely",
            );
            const facts = u.extracted_facts.filter((f) => f.evidence.value !== null);
            return (
              <li key={u.id}>
                {previews[u.id] && <img className="evidence-thumb" src={previews[u.id]} alt="" />}
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
