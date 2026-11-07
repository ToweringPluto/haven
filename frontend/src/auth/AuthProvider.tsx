import { Auth0Provider, useAuth0, type AppState } from "@auth0/auth0-react";
import { createContext, use, useMemo, type ReactNode } from "react";
import { auth0Config, isAuthConfigured } from "./config";

export interface AuthUser {
  name?: string;
  email?: string;
}

export interface AuthValue {
  /** False when the Auth0 env vars are missing; signed-in features then run in sample mode. */
  isConfigured: boolean;
  isLoading: boolean;
  isAuthenticated: boolean;
  user: AuthUser | null;
  login: () => void;
  logout: () => void;
  /** Resolves to an API access token, or null if the user isn't (or can't silently be) signed in. */
  getAccessToken: () => Promise<string | null>;
}

const SIGNED_OUT: AuthValue = {
  isConfigured: false,
  isLoading: false,
  isAuthenticated: false,
  user: null,
  login: () => {},
  logout: () => {},
  getAccessToken: async () => null,
};

const AuthContext = createContext<AuthValue>(SIGNED_OUT);

/** Return to the page the user started login from (we use hash routes, e.g. `#/screening`). */
function onRedirectCallback(appState?: AppState) {
  const returnTo = typeof appState?.returnTo === "string" ? appState.returnTo : "#/";
  window.history.replaceState({}, document.title, window.location.pathname + returnTo);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

function Auth0Bridge({ children }: { children: ReactNode }) {
  const {
    isLoading,
    isAuthenticated,
    user,
    loginWithRedirect,
    logout,
    getAccessTokenSilently,
  } = useAuth0();

  const value = useMemo<AuthValue>(
    () => ({
      isConfigured: true,
      isLoading,
      isAuthenticated,
      user: isAuthenticated && user ? { name: user.name, email: user.email } : null,
      login: () =>
        void loginWithRedirect({ appState: { returnTo: window.location.hash || "#/" } }),
      logout: () => void logout({ logoutParams: { returnTo: window.location.origin } }),
      getAccessToken: async () => {
        if (!isAuthenticated) return null;
        try {
          return (await getAccessTokenSilently()) || null;
        } catch {
          // login_required, consent_required, network errors… treat as signed out.
          return null;
        }
      },
    }),
    [isLoading, isAuthenticated, user, loginWithRedirect, logout, getAccessTokenSilently],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (!isAuthConfigured) return <AuthContext value={SIGNED_OUT}>{children}</AuthContext>;

  return (
    <Auth0Provider
      domain={auth0Config.domain}
      clientId={auth0Config.clientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
        audience: auth0Config.audience,
        scope: "openid profile email",
      }}
      // Refresh-token rotation keeps users signed in across reloads without relying on
      // third-party cookies (which most browsers now block for silent auth).
      useRefreshTokens
      cacheLocation="localstorage"
      onRedirectCallback={onRedirectCallback}
    >
      <Auth0Bridge>{children}</Auth0Bridge>
    </Auth0Provider>
  );
}

export const useAuth = () => use(AuthContext);
