import { createContext, use, useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";

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
}

const ShortlistContext = createContext<ShortlistValue | null>(null);

const toggle = (ids: string[], id: string) =>
  ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];

export function ShortlistProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<string[]>([]);
  const [compare, setCompare] = useState<string[]>([]);

  const isSaved = useCallback((id: string) => saved.includes(id), [saved]);
  const toggleSaved = useCallback((id: string) => setSaved((s) => toggle(s, id)), []);
  const toggleCompare = useCallback((id: string) => setCompare((c) => toggle(c, id)), []);
  const addToCompare = useCallback(
    (id: string) => setCompare((c) => (c.includes(id) ? c : [...c, id])),
    [],
  );
  const clearCompare = useCallback(() => setCompare([]), []);

  const value = useMemo(
    () => ({ saved, compare, isSaved, toggleSaved, toggleCompare, addToCompare, clearCompare }),
    [saved, compare, isSaved, toggleSaved, toggleCompare, addToCompare, clearCompare],
  );
  return <ShortlistContext value={value}>{children}</ShortlistContext>;
}

export function useShortlist() {
  const value = use(ShortlistContext);
  if (!value) throw new Error("useShortlist must be used inside <ShortlistProvider>");
  return value;
}
