import { useAuth } from "../auth/AuthProvider";
import { Button } from "./Button";

interface LoginButtonProps {
  label?: string;
  /** Render as a plain text link (nav) instead of the primary button. */
  variant?: "button" | "text";
}

/** Hidden when auth isn't configured or the user is already signed in. */
export function LoginButton({ label = "Sign in", variant = "button" }: LoginButtonProps) {
  const { isConfigured, isAuthenticated, isLoading, login } = useAuth();
  if (!isConfigured || isAuthenticated) return null;

  return variant === "text" ? (
    <button type="button" className="text-button" onClick={login} disabled={isLoading}>
      {label}
    </button>
  ) : (
    <Button onClick={login} disabled={isLoading}>
      {label}
    </Button>
  );
}
