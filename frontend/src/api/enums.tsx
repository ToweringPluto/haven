import { createContext, use, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./client";

import type { EnumOption } from "./types";

type EnumLabels = Record<string, Record<string, string>>;
type EnumsState = { labels: EnumLabels; options: Record<string, EnumOption[]> };

const EnumsContext = createContext<EnumsState>({ labels: {}, options: {} });

/** Loads the server's human labels (GET /v1/meta/enums) once for the whole app. */
export function EnumsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<EnumsState>({ labels: {}, options: {} });

  useEffect(() => {
    api.enums().then((res) => {
      if (res.status !== "ok") return; // fall back to raw values; nothing else depends on this
      const out: EnumLabels = {};
      for (const [name, options] of Object.entries(res.data.enums)) {
        out[name] = Object.fromEntries(options.map((o) => [o.value, o.label]));
      }
      setState({ labels: out, options: res.data.enums });
    });
  }, []);

  return <EnumsContext value={state}>{children}</EnumsContext>;
}

/**
 * `label("origin", "listing")` → "From the listing". Unknown values (or labels that haven't
 * loaded yet) fall back to a readable form of the raw value, as the contract requires.
 */
export function useEnumLabel() {
  const { labels } = use(EnumsContext);
  return useMemo(
    () => (name: string, value: string | null | undefined) => {
      if (value === null || value === undefined) return "";
      return labels[name]?.[value] ?? humanise(value);
    },
    [labels],
  );
}

/** The server's values for an enum, or `fallback` until they load (or if they fail to). */
export function useEnumValues(name: string, fallback: readonly string[]): string[] {
  const { options } = use(EnumsContext);
  return options[name]?.map((o) => o.value) ?? [...fallback];
}

const humanise = (value: string) => {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};
