import type { ReactNode } from "react";

// Defined once at module scope so the SVG elements aren't rebuilt on every render.
const ICON_PATHS = {
  arrow: (
    <>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 18 6-6-6-6" />,
  heart: (
    <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5a5.5 5.5 0 0 0 1-8.9Z" />
  ),
  home: (
    <>
      <path d="m3 11 9-8 9 8" />
      <path d="M5 10v10h14V10" />
      <path d="M9 20v-6h6v6" />
    </>
  ),
  map: (
    <>
      <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z" />
      <path d="M9 3v15M15 6v15" />
    </>
  ),
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </>
  ),
  shield: (
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
      <path d="m9 12 2 2 4-5" />
    </>
  ),
  spark: (
    <path d="m12 3-1.4 4.1a5 5 0 0 1-3.2 3.2L3 12l4.4 1.6a5 5 0 0 1 3.2 3.2L12 21l1.5-4.2a5 5 0 0 1 3.1-3.1L21 12l-4.4-1.7a5 5 0 0 1-3.1-3.1Z" />
  ),
  upload: (
    <>
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M5 15v5h14v-5" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
  x: <path d="m6 6 12 12M18 6 6 18" />,
  zap: <path d="m13 2-9 12h8l-1 8 9-12h-8Z" />,
  train: (
    <>
      <rect x="5" y="3" width="14" height="15" rx="3" />
      <path d="M8 21l2-3M16 18l2 3M5 11h14M9 7h6" />
    </>
  ),
  wallet: (
    <>
      <path d="M3 6h16v14H3z" />
      <path d="M3 6l13-3v3M15 12h6v5h-6z" />
    </>
  ),
  access: (
    <>
      <circle cx="12" cy="4" r="2" />
      <path d="M12 7v6l-3 8M12 10l5 3M8 9l4 1M14 13l4 7" />
    </>
  ),
  leaf: (
    <>
      <path d="M20 4C12 4 5 8 5 15c0 3 2 5 5 5 7 0 10-8 10-16Z" />
      <path d="M4 21c3-6 7-9 13-12" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 7h.01" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof ICON_PATHS;

interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
}

export function Icon({ name, size = 20, className }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICON_PATHS[name]}
    </svg>
  );
}
