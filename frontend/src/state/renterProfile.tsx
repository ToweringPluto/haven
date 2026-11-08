import { createContext, use, useCallback, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import type { Priority, ProfileInput, RenterProfile } from "../api/types";
import {
  DESTINATIONS,
  PERSONAS,
  accessKeys,
  accessRequirements,
  type AccessKey,
} from "../data/onboarding";

/** What the renter has told us, in the shape the onboarding UI edits. */
export interface ProfileDraft {
  budget: number;
  areas: string[];
  access: AccessKey[];
  priorities: Priority[];
  destinationIds: string[];
  maxTravelMinutes: number;
}

/** The profile the server knows about; its id is what cost/suitability/reports use. */
export interface SavedProfile {
  id: string;
  label: string;
  personaId: string | null;
}

interface RenterProfileValue {
  draft: ProfileDraft;
  updateDraft: (patch: Partial<ProfileDraft>) => void;
  saved: SavedProfile | null;
  /** Saves the draft as a new server profile. Returns an error message, or null on success. */
  saveProfile: () => Promise<string | null>;
  /** Switches to one of the illustrative personas (full suitability results). */
  choosePersona: (personaId: string) => Promise<string | null>;
  clearProfile: () => void;
}

const DEFAULT_DRAFT: ProfileDraft = {
  budget: 1250,
  areas: [],
  access: [],
  priorities: [],
  destinationIds: [],
  maxTravelMinutes: 40,
};

function toInput(draft: ProfileDraft): ProfileInput {
  return {
    label: "My renter profile",
    monthly_budget_gbp: draft.budget,
    priorities: draft.priorities,
    access: accessRequirements(draft.access.filter((k) => k !== "none")),
    destinations: DESTINATIONS.filter((d) => draft.destinationIds.includes(d.id)).map(
      ({ id: _id, ...d }) => ({ ...d, max_travel_minutes: draft.maxTravelMinutes }),
    ),
    other_recurring_costs: [],
  };
}

function fromProfile(profile: RenterProfile, current: ProfileDraft): ProfileDraft {
  return {
    ...current,
    budget: profile.monthly_budget_gbp ?? current.budget,
    access: accessKeys(profile.access),
    priorities: profile.priorities,
    destinationIds: DESTINATIONS.filter((d) =>
      profile.destinations.some((p) => p.name === d.name),
    ).map((d) => d.id),
  };
}

const RenterProfileContext = createContext<RenterProfileValue | null>(null);

export function RenterProfileProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState(DEFAULT_DRAFT);
  const [saved, setSaved] = useState<SavedProfile | null>(null);
  const { getAccessToken } = useAuth();

  const updateDraft = useCallback(
    (patch: Partial<ProfileDraft>) => setDraft((d) => ({ ...d, ...patch })),
    [],
  );

  const saveProfile = useCallback(async () => {
    // Signed in: the profile is saved to the account. Signed out: it's private to its id.
    const token = await getAccessToken().catch(() => null);
    const res = await api.createProfile(toInput(draft), token);
    if (res.status !== "ok") return res.message;
    setSaved({ id: res.data.id, label: "Your profile", personaId: null });
    return null;
  }, [draft, getAccessToken]);

  const choosePersona = useCallback(async (personaId: string) => {
    const res = await api.profile(personaId);
    if (res.status !== "ok") return res.message;
    const persona = PERSONAS.find((p) => p.id === personaId);
    setSaved({ id: res.data.id, label: persona?.name ?? res.data.label, personaId });
    setDraft((d) => fromProfile(res.data, d));
    return null;
  }, []);

  const clearProfile = useCallback(() => setSaved(null), []);

  const value = useMemo(
    () => ({ draft, updateDraft, saved, saveProfile, choosePersona, clearProfile }),
    [draft, updateDraft, saved, saveProfile, choosePersona, clearProfile],
  );
  return <RenterProfileContext value={value}>{children}</RenterProfileContext>;
}

export function useRenterProfile() {
  const value = use(RenterProfileContext);
  if (!value) throw new Error("useRenterProfile must be used inside <RenterProfileProvider>");
  return value;
}
