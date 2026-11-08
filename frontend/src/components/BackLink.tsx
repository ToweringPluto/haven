import { useNavigation } from "../state/navigation";
import type { Page } from "../types";

export function BackLink({ to, param, children }: { to: Page; param?: string; children: string }) {
  const { go } = useNavigation();
  return (
    <button type="button" className="back-link" onClick={() => go(to, param)}>
      ← {children}
    </button>
  );
}
