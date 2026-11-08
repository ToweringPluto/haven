import { useState } from "react";
import { PERSONAS } from "../data/onboarding";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";
import { Icon } from "./Icon";

/** Whose needs the assessments are for, with a quick switch to an example renter. */
export function ProfileBar() {
  const { go } = useNavigation();
  const { saved, choosePersona, clearProfile } = useRenterProfile();
  const [error, setError] = useState<string | null>(null);

  const pick = async (id: string) => {
    setError(id ? await choosePersona(id) : (clearProfile(), null));
  };

  return (
    <div className="profile-bar">
      <Icon name="user" size={18} />
      {!saved && (
        <span>
          No renter profile yet: costs aren’t compared with a budget and requirement checks are off.
        </span>
      )}
      <label>
        <span className="visually-hidden">Example renter</span>
        <select value={saved?.personaId ?? ""} onChange={(e) => pick(e.target.value)}>
          <option value="">{saved && !saved.personaId ? "Your profile" : "Try an example renter…"}</option>
          {PERSONAS.map((p) => (
            <option key={p.id} value={p.id}>
              Example: {p.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="text-button" onClick={() => go("onboarding")}>
        {saved && !saved.personaId ? "Edit your profile" : "Create your profile"}
      </button>
      {error && <small role="alert">{error}</small>}
    </div>
  );
}
