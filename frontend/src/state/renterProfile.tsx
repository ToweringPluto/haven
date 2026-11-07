import { createContext, use, useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";

export interface RenterProfile {
  budget: number;
  areas: string[];
  access: string[];
  priorities: string[];
  destinations: string[];
}

interface RenterProfileValue {
  profile: RenterProfile;
  updateProfile: (patch: Partial<RenterProfile>) => void;
}

const DEFAULT_PROFILE: RenterProfile = {
  budget: 1250,
  areas: ["Leith", "Stockbridge"],
  access: ["Step-free entrance"],
  priorities: [],
  destinations: ["University of Edinburgh"],
};

const RenterProfileContext = createContext<RenterProfileValue | null>(null);

export function RenterProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const updateProfile = useCallback(
    (patch: Partial<RenterProfile>) => setProfile((p) => ({ ...p, ...patch })),
    [],
  );
  const value = useMemo(() => ({ profile, updateProfile }), [profile, updateProfile]);
  return <RenterProfileContext value={value}>{children}</RenterProfileContext>;
}

export function useRenterProfile() {
  const value = use(RenterProfileContext);
  if (!value) throw new Error("useRenterProfile must be used inside <RenterProfileProvider>");
  return value;
}
