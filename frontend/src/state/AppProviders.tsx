import type { ReactNode } from "react";
import { AuthProvider } from "../auth/AuthProvider";
import { NavigationProvider } from "./navigation";
import { RenterProfileProvider } from "./renterProfile";
import { ShortlistProvider } from "./shortlist";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <NavigationProvider>
        <RenterProfileProvider>
          <ShortlistProvider>{children}</ShortlistProvider>
        </RenterProfileProvider>
      </NavigationProvider>
    </AuthProvider>
  );
}
