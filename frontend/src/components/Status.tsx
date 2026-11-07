import type { ReactNode } from "react";
import type { StatusType } from "../types";

const STATUS_SYMBOL: Record<StatusType, string> = { good: "✓", warn: "!", info: "?" };

export const STATUS_LABEL: Record<StatusType, string> = {
  good: "Suitable",
  warn: "Potential concern",
  info: "More information needed",
};

/** Status pill; defaults to the standard label for its type. */
export function Status({ type, children }: { type: StatusType; children?: ReactNode }) {
  return (
    <span className={`status status-${type}`}>
      <span aria-hidden="true">{STATUS_SYMBOL[type]}</span>
      {children ?? STATUS_LABEL[type]}
    </span>
  );
}
