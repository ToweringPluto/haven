import { useAuth } from "../auth/AuthProvider";
import { Icon } from "./Icon";

/** Signed-in user's name (or email). Renders nothing when signed out. */
export function UserBadge({ onClick }: { onClick?: () => void }) {
  const { isAuthenticated, user } = useAuth();
  const label = user?.name || user?.email;
  if (!isAuthenticated || !label) return null;

  return (
    <button type="button" className="user-badge" onClick={onClick} title={user?.email}>
      <Icon name="user" size={16} />
      <span>{label}</span>
    </button>
  );
}
