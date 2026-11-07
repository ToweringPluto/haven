import { createContext, use, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { PAGES, type Page } from "../types";

interface NavigationValue {
  page: Page;
  go: (page: Page) => void;
}

const NavigationContext = createContext<NavigationValue | null>(null);

/** Reads the page from a `#/page` URL hash so links, refresh and the back button work. */
function pageFromHash(): Page {
  const slug = window.location.hash.replace(/^#\/?/, "");
  return (PAGES as readonly string[]).includes(slug) ? (slug as Page) : "home";
}

const scrollToTop = () => window.scrollTo({ top: 0, behavior: "smooth" });

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState<Page>(pageFromHash);

  useEffect(() => {
    const onHashChange = () => {
      setPage(pageFromHash());
      scrollToTop();
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const go = useCallback((next: Page) => {
    if (next === pageFromHash()) scrollToTop();
    else window.location.hash = next === "home" ? "/" : `/${next}`;
  }, []);

  const value = useMemo(() => ({ page, go }), [page, go]);
  return <NavigationContext value={value}>{children}</NavigationContext>;
}

export function useNavigation() {
  const value = use(NavigationContext);
  if (!value) throw new Error("useNavigation must be used inside <NavigationProvider>");
  return value;
}
