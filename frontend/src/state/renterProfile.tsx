import {
  createContext,
  use,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
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
  /** The example renter this is, or null for the renter's own profile. */
  personaId: string | null;
  /** True when the profile is saved to the signed-in user's account (editable, deletable). */
  owned: boolean;
}

interface RenterProfileValue {
  draft: ProfileDraft;
  updateDraft: (patch: Partial<ProfileDraft>) => void;
  saved: SavedProfile | null;
  /** Saves the draft: updates the renter's own profile, or creates one. Error message or null. */
  saveProfile: () => Promise<string | null>;
  /** Switches to one of the example renters. */
  choosePersona: (personaId: string) => Promise<string | null>;
  /** Stops assessing for a profile (nothing is deleted). */
  clearProfile: () => void;
  /** Deletes the renter's own saved profile from their account. */
  deleteProfile: () => Promise<string | null>;
  /** Forgets everything locally (after "delete all my data"). */
  reset: () => void;
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
    preferred_areas: draft.areas,
  };
}

function fromProfile(profile: RenterProfile | ProfileInput, current: ProfileDraft): ProfileDraft {
  const travel = profile.destinations.find((d) => d.max_travel_minutes)?.max_travel_minutes;
  return {
    budget: profile.monthly_budget_gbp ?? current.budget,
    areas: profile.preferred_areas ?? [],
    access: accessKeys(profile.access),
    priorities: profile.priorities,
    destinationIds: DESTINATIONS.filter((d) =>
      profile.destinations.some((p) => p.name === d.name),
    ).map((d) => d.id),
    maxTravelMinutes: travel ?? current.maxTravelMinutes,
  };
}

const RenterProfileContext = createContext<RenterProfileValue | null>(null);

export function RenterProfileProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState(DEFAULT_DRAFT);
  const [saved, setSaved] = useState<SavedProfile | null>(null);
  const { isAuthenticated, getAccessToken } = useAuth();
  // Profiles made for the lower-budget demo renters, so switching back reuses them.
  const presetProfiles = useRef(new Map<string, string>());

  const token = useCallback(() => getAccessToken().catch(() => null), [getAccessToken]);

  // On sign-in, pick up the renter's most recent saved profile (unless they've chosen one).
  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    void (async () => {
      const res = await api.profiles(await token());
      if (cancelled || res.status !== "ok") return;
      const sampleIds = new Set(PERSONAS.map((p) => p.id));
      const own = res.data.items.filter((p) => !sampleIds.has(p.id));
      const latest = own.at(-1);
      if (!latest) return;
      setSaved((current) => {
        if (current) return current;
        setDraft((d) => fromProfile(latest, d));
        return { id: latest.id, label: "Your profile", personaId: null, owned: true };
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, token]);

  const updateDraft = useCallback(
    (patch: Partial<ProfileDraft>) => setDraft((d) => ({ ...d, ...patch })),
    [],
  );

  const saveProfile = useCallback(async () => {
    const accessToken = await token();
    const input = toInput(draft);
    // Signed in: update the profile already on the account, or save a new one to it.
    // Signed out: a new profile that is private to its id.
    const res =
      saved?.owned && accessToken
        ? await api.updateProfile(saved.id, input, accessToken)
        : await api.createProfile(input, accessToken);
    if (res.status !== "ok") return res.message;
    setSaved({ id: res.data.id, label: "Your profile", personaId: null, owned: !!accessToken });
    return null;
  }, [draft, saved, token]);

  const choosePersona = useCallback(async (personaId: string) => {
    const persona = PERSONAS.find((p) => p.id === personaId);
    if (persona?.preset) {
      let profileId = presetProfiles.current.get(personaId);
      if (!profileId) {
        // Not saved to the account: it's an example, not the renter's own profile.
        const res = await api.createProfile(persona.preset, null);
        if (res.status !== "ok") return res.message;
        profileId = res.data.id;
        presetProfiles.current.set(personaId, profileId);
      }
      setSaved({ id: profileId, label: persona.name, personaId, owned: false });
      setDraft((d) => fromProfile(persona.preset!, d));
      return null;
    }
    const res = await api.profile(personaId);
    if (res.status !== "ok") return res.message;
    setSaved({ id: res.data.id, label: persona?.name ?? res.data.label, personaId, owned: false });
    setDraft((d) => fromProfile(res.data, d));
    return null;
  }, []);

  const clearProfile = useCallback(() => setSaved(null), []);

  const deleteProfile = useCallback(async () => {
    if (!saved?.owned) return null;
    const res = await api.deleteProfile(saved.id, await token());
    if (res.status !== "ok" && res.status !== "not_found") return res.message;
    setSaved(null);
    setDraft(DEFAULT_DRAFT);
    return null;
  }, [saved, token]);

  const reset = useCallback(() => {
    setSaved(null);
    setDraft(DEFAULT_DRAFT);
    presetProfiles.current.clear();
  }, []);

  const value = useMemo(
    () => ({
      draft,
      updateDraft,
      saved,
      saveProfile,
      choosePersona,
      clearProfile,
      deleteProfile,
      reset,
    }),
    [draft, updateDraft, saved, saveProfile, choosePersona, clearProfile, deleteProfile, reset],
  );
  return <RenterProfileContext value={value}>{children}</RenterProfileContext>;
}

export function useRenterProfile() {
  const value = use(RenterProfileContext);
  if (!value) throw new Error("useRenterProfile must be used inside <RenterProfileProvider>");
  return value;
}
