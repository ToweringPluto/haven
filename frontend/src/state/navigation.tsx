import { createContext, use, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { prefersReducedMotion } from "../map/motion";
import { PAGES, type Page } from "../types";

interface Route {
  page: Page;
  /** Optional id from `#/page/<param>`, e.g. a property or report id. */
  param: string | null;
}

interface NavigationValue extends Route {
  go: (page: Page, param?: string) => void;
}

const NavigationContext = createContext<NavigationValue | null>(null);

/** Reads `#/page` or `#/page/<param>` so links, refresh and the back button work. */
function routeFromHash(): Route {
  const [slug = "", ...rest] = window.location.hash.replace(/^#\/?/, "").split("/");
  const param = rest.length ? decodeURIComponent(rest.join("/")) : null;
  return (PAGES as readonly string[]).includes(slug)
    ? { page: slug as Page, param }
    : { page: "home", param: null };
}

const hashFor = (page: Page, param?: string) =>
  page === "home" ? "#/" : `#/${page}${param ? `/${encodeURIComponent(param)}` : ""}`;

const scrollToTop = () =>
  window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<Route>(routeFromHash);

  useEffect(() => {
    const onHashChange = () => {
      setRoute(routeFromHash());
      scrollToTop();
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const go = useCallback((page: Page, param?: string) => {
    const next = hashFor(page, param);
    if (next === window.location.hash || (next === "#/" && !window.location.hash)) scrollToTop();
    else window.location.hash = next;
  }, []);

  const value = useMemo(() => ({ ...route, go }), [route, go]);
  return <NavigationContext value={value}>{children}</NavigationContext>;
}

export function useNavigation() {
  const value = use(NavigationContext);
  if (!value) throw new Error("useNavigation must be used inside <NavigationProvider>");
  return value;
}
