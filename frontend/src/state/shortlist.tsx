import { createContext, use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthProvider";

interface ShortlistValue {
  /** IDs of properties the renter has saved. */
  saved: string[];
  /** IDs of properties selected for side-by-side comparison. */
  compare: string[];
  isSaved: (id: string) => boolean;
  toggleSaved: (id: string) => void;
  toggleCompare: (id: string) => void;
  addToCompare: (id: string) => void;
  clearCompare: () => void;
  /** Forgets the saved homes locally (after "delete all my data"). */
  reset: () => void;
  /** Why the last save to the account failed, if it did. */
  syncError: string | null;
}

const ShortlistContext = createContext<ShortlistValue | null>(null);

// Signed out, saved homes are kept in this browser so a refresh doesn't lose them.
const STORAGE_KEY = "haven.savedHomes";

function readLocal(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

function writeLocal(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // Storage blocked (private window etc.): saved homes last for this visit only.
  }
}

const toggle = (ids: string[], id: string) =>
  ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];

export function ShortlistProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, getAccessToken } = useAuth();
  const [saved, setSaved] = useState<string[]>(readLocal);
  const [compare, setCompare] = useState<string[]>([]);
  const [syncError, setSyncError] = useState<string | null>(null);
  // True once the account's list has been loaded, so we never overwrite it with a stale one.
  const synced = useRef(false);

  // On sign-in: merge what was saved while signed out into the account's list.
  useEffect(() => {
    synced.current = false;
    if (!isAuthenticated) return;
    let cancelled = false;
    void (async () => {
      const token = await getAccessToken().catch(() => null);
      const res = await api.savedHomes(token);
      if (cancelled || res.status !== "ok") return;
      const local = readLocal();
      const merged = [...new Set([...res.data.property_ids, ...local])];
      synced.current = true;
      setSaved(merged);
      if (merged.length !== res.data.property_ids.length) {
        await api.setSavedHomes(merged, token);
      }
      writeLocal([]);
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, getAccessToken]);

  const persist = useCallback(
    async (ids: string[]) => {
      if (!isAuthenticated) return writeLocal(ids);
      if (!synced.current) return;
      const res = await api.setSavedHomes(ids, await getAccessToken().catch(() => null));
      setSyncError(res.status === "ok" ? null : `Couldn’t save to your account: ${res.message}`);
    },
    [isAuthenticated, getAccessToken],
  );

  const toggleSaved = useCallback(
    (id: string) =>
      setSaved((s) => {
        const next = toggle(s, id);
        void persist(next);
        return next;
      }),
    [persist],
  );
  const isSaved = useCallback((id: string) => saved.includes(id), [saved]);
  const toggleCompare = useCallback((id: string) => setCompare((c) => toggle(c, id)), []);
  const addToCompare = useCallback(
    (id: string) => setCompare((c) => (c.includes(id) ? c : [...c, id])),
    [],
  );
  const clearCompare = useCallback(() => setCompare([]), []);
  const reset = useCallback(() => {
    setSaved([]);
    setCompare([]);
    writeLocal([]);
  }, []);

  const value = useMemo(
    () => ({
      saved,
      compare,
      isSaved,
      toggleSaved,
      toggleCompare,
      addToCompare,
      clearCompare,
      reset,
      syncError,
    }),
    [saved, compare, isSaved, toggleSaved, toggleCompare, addToCompare, clearCompare, reset, syncError],
  );
  return <ShortlistContext value={value}>{children}</ShortlistContext>;
}

export function useShortlist() {
  const value = use(ShortlistContext);
  if (!value) throw new Error("useShortlist must be used inside <ShortlistProvider>");
  return value;
}
