import type { Loaded } from "../api/client";
import { Icon } from "./Icon";

/** Renders a failed load. 501 reads as "not available yet", not as a fault (guide §5). */
export function LoadProblem({
  result,
  onRetry,
  unavailableHint,
}: {
  result: Exclude<Loaded<unknown>, { status: "ok" }>;
  onRetry?: () => void;
  unavailableHint?: string;
}) {
  const heading =
    result.status === "unavailable"
      ? "Not available yet"
      : result.status === "not_found"
        ? "Not found"
        : "Something went wrong";

  return (
    <div className={`load-problem is-${result.status}`} role="status">
      <Icon name="info" size={18} />
      <div>
        <b>{heading}</b>
        <p>{result.message}</p>
        {result.status === "unavailable" && unavailableHint && <p>{unavailableHint}</p>}
      </div>
      {onRetry && result.status === "error" && (
        <button type="button" className="text-button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
