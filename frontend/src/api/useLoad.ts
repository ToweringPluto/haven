import { useCallback, useEffect, useState } from "react";
import type { Loaded } from "./client";

export type LoadState<T> = { status: "loading" } | Loaded<T>;

/**
 * Runs `load` whenever `key` changes (pass `null` to skip). Ignores responses that arrive
 * after the key changed, so fast navigation never shows another property's data.
 */
export function useLoad<T>(key: string | null, load: () => Promise<Loaded<T>>) {
  const [state, setState] = useState<{ key: string | null; value: LoadState<T> }>({
    key: null,
    value: { status: "loading" },
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (key === null) return;
    let current = true;
    setState({ key, value: { status: "loading" } });
    load().then((value) => current && setState({ key, value }));
    return () => {
      current = false;
    };
    // `load` is recreated each render; `key` captures what it depends on.
  }, [key, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const value: LoadState<T> = state.key === key ? state.value : { status: "loading" };
  return [value, reload] as const;
}
