import { lazy, Suspense, useEffect, type ComponentType, type LazyExoticComponent } from "react";
import { AuthErrorBanner } from "./components/AuthErrorBanner";
import { Footer } from "./components/Footer";
import { Nav } from "./components/Nav";
import HomePage from "./pages/HomePage";
import { AppProviders } from "./state/AppProviders";
import { useNavigation } from "./state/navigation";
import type { Page } from "./types";

type PageModule = Promise<{ default: ComponentType }>;

// Every page except the landing page is split into its own chunk.
const PAGE_LOADERS: Record<Exclude<Page, "home">, () => PageModule> = {
  onboarding: () => import("./pages/Onboarding"),
  explore: () => import("./pages/Explore"),
  property: () => import("./pages/PropertyDetail"),
  screening: () => import("./pages/Screening"),
  compare: () => import("./pages/Compare"),
  dashboard: () => import("./pages/Dashboard"),
  about: () => import("./pages/About"),
};

const PAGE_COMPONENTS: Record<Page, ComponentType | LazyExoticComponent<ComponentType>> = {
  home: HomePage,
  onboarding: lazy(PAGE_LOADERS.onboarding),
  explore: lazy(PAGE_LOADERS.explore),
  property: lazy(PAGE_LOADERS.property),
  screening: lazy(PAGE_LOADERS.screening),
  compare: lazy(PAGE_LOADERS.compare),
  dashboard: lazy(PAGE_LOADERS.dashboard),
  about: lazy(PAGE_LOADERS.about),
};

/** Warms the page chunks once the browser is idle so later navigation doesn't wait on the network. */
function usePrefetchPages() {
  useEffect(() => {
    const prefetch = () => Object.values(PAGE_LOADERS).forEach((load) => void load());
    if ("requestIdleCallback" in window) {
      const id = window.requestIdleCallback(prefetch, { timeout: 3000 });
      return () => window.cancelIdleCallback(id);
    }
    const id = setTimeout(prefetch, 1500);
    return () => clearTimeout(id);
  }, []);
}

function CurrentPage() {
  const { page } = useNavigation();
  const PageComponent = PAGE_COMPONENTS[page];
  return (
    <Suspense fallback={<main className="shell" style={{ minHeight: "70vh" }} aria-busy="true" />}>
      <PageComponent />
    </Suspense>
  );
}

export default function App() {
  usePrefetchPages();
  return (
    <AppProviders>
      <Nav />
      <AuthErrorBanner />
      <CurrentPage />
      <Footer />
    </AppProviders>
  );
}
