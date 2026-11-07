import { useNavigation } from "../state/navigation";
import type { Page } from "../types";

export function BackLink({ to, children }: { to: Page; children: string }) {
  const { go } = useNavigation();
  return (
    <button type="button" className="back-link" onClick={() => go(to)}>
      ← {children}
    </button>
  );
}
