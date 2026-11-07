import { useAuth } from "../auth/AuthProvider";

export function LogoutButton() {
  const { isAuthenticated, logout } = useAuth();
  if (!isAuthenticated) return null;

  return (
    <button type="button" className="text-button" onClick={logout}>
      Sign out
    </button>
  );
}
