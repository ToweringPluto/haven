import { useAuth } from "../auth/AuthProvider";
import { SIGN_IN_MESSAGE } from "../auth/authFetch";
import { Icon } from "./Icon";
import { LoginButton } from "./LoginButton";

/** Inline nudge to sign in. Shows only the message when auth isn't configured. */
export function SignInPrompt({ message = SIGN_IN_MESSAGE }: { message?: string }) {
  const { isConfigured } = useAuth();
  return (
    <div className="auth-prompt" role="status">
      <Icon name="user" size={18} />
      <span>{isConfigured ? message : `${message} (sign-in isn’t set up in this demo).`}</span>
      <LoginButton />
    </div>
  );
}
