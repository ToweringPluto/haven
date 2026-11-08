import type { ReactNode } from "react";
import { EnumsProvider } from "../api/enums";
import { AuthProvider } from "../auth/AuthProvider";
import { AccessibilityProvider } from "./accessibility";
import { NavigationProvider } from "./navigation";
import { RenterProfileProvider } from "./renterProfile";
import { ShortlistProvider } from "./shortlist";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AccessibilityProvider>
      <AuthProvider>
        <EnumsProvider>
          <NavigationProvider>
            <RenterProfileProvider>
              <ShortlistProvider>{children}</ShortlistProvider>
            </RenterProfileProvider>
          </NavigationProvider>
        </EnumsProvider>
      </AuthProvider>
    </AccessibilityProvider>
  );
}
