const env = import.meta.env;

export const auth0Config = {
  domain: env.VITE_AUTH0_DOMAIN?.trim() ?? "",
  clientId: env.VITE_AUTH0_CLIENT_ID?.trim() ?? "",
  audience: env.VITE_AUTH0_AUDIENCE?.trim() ?? "",
};

/**
 * Auth is optional: without these variables the app runs in public/sample mode only,
 * so the demo never depends on Auth0 being set up.
 */
export const isAuthConfigured = Boolean(
  auth0Config.domain && auth0Config.clientId && auth0Config.audience,
);

export const API_BASE_URL = (env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

/** URL of a pre-generated file in `public/samples/`. */
export const sampleUrl = (file: string) => `${import.meta.env.BASE_URL}samples/${file}`;
