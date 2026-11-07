import type { ReactNode } from "react";
import { NavigationProvider } from "./navigation";
import { RenterProfileProvider } from "./renterProfile";
import { ShortlistProvider } from "./shortlist";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <NavigationProvider>
      <RenterProfileProvider>
        <ShortlistProvider>{children}</ShortlistProvider>
      </RenterProfileProvider>
    </NavigationProvider>
  );
}
