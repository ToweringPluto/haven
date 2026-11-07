import { useAuth } from "../auth/AuthProvider";
import { Icon } from "./Icon";

/** Shows why sign-in failed instead of silently landing back on the page. */
export function AuthErrorBanner() {
  const { error, dismissError, login } = useAuth();
  if (!error) return null;

  return (
    <div className="auth-error shell" role="alert">
      <Icon name="info" size={18} />
      <p>
        <b>Sign-in didn’t complete.</b> {error} The rest of Haven still works without signing in.
      </p>
      <button type="button" className="text-button" onClick={login}>
        Try again
      </button>
      <button type="button" className="text-button" onClick={dismissError} aria-label="Dismiss">
        <Icon name="x" size={16} />
      </button>
    </div>
  );
}
