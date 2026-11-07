import type { ReactNode } from "react";
import { EnumsProvider } from "../api/enums";
import { AuthProvider } from "../auth/AuthProvider";
import { NavigationProvider } from "./navigation";
import { RenterProfileProvider } from "./renterProfile";
import { ShortlistProvider } from "./shortlist";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <EnumsProvider>
      <NavigationProvider>
        <RenterProfileProvider>
          <ShortlistProvider>{children}</ShortlistProvider>
        </RenterProfileProvider>
      </NavigationProvider>
      </EnumsProvider>
    </AuthProvider>
  );
}
