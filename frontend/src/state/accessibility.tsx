import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

/**
 * Display and reading preferences. They're kept in this browser (localStorage), so they work
 * signed out and apply before anything loads; they never leave the device.
 *
 * Each setting becomes a `data-*` attribute (or CSS variable) on <html>; index.css does the
 * rest. `index.html` applies the saved theme before React starts so there's no flash.
 */
export type ThemeChoice = "system" | "light" | "dark";
export type FontChoice = "default" | "lexend" | "atkinson" | "opendyslexic";

export interface AccessibilitySettings {
  theme: ThemeChoice;
  highContrast: boolean;
  font: FontChoice;
  /** Text size multiplier (1 = 100%). */
  textScale: number;
  wideSpacing: boolean;
  reduceMotion: boolean;
  underlineLinks: boolean;
  strongFocus: boolean;
  /** Read-aloud speed multiplier (1 = normal). */
  speechRate: number;
}

export const DEFAULT_SETTINGS: AccessibilitySettings = {
  theme: "system",
  highContrast: false,
  font: "default",
  textScale: 1,
  wideSpacing: false,
  reduceMotion: false,
  underlineLinks: false,
  strongFocus: false,
  speechRate: 1,
};

export const TEXT_SCALES = [1, 1.15, 1.3, 1.5] as const;
export const SPEECH_RATES = [0.75, 1, 1.25, 1.5] as const;

/** Fonts loaded only when chosen, so nobody downloads a font they don't use. */
const FONT_STYLESHEETS: Record<Exclude<FontChoice, "default">, string> = {
  lexend: "https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap",
  atkinson:
    "https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap",
  opendyslexic: "https://fonts.cdnfonts.com/css/opendyslexic",
};

export const STORAGE_KEY = "haven.accessibility";

function load(): AccessibilitySettings {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    if (raw && typeof raw === "object") return { ...DEFAULT_SETTINGS, ...raw };
  } catch {
    // Storage blocked or corrupt: fall back to the defaults.
  }
  return DEFAULT_SETTINGS;
}

function save(settings: AccessibilitySettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Private window or storage blocked: settings still apply for this visit.
  }
}

const darkQuery = () => window.matchMedia("(prefers-color-scheme: dark)");

function ensureFont(font: FontChoice) {
  if (font === "default") return;
  const id = `a11y-font-${font}`;
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = FONT_STYLESHEETS[font];
  document.head.append(link);
}

function apply(settings: AccessibilitySettings, systemDark: boolean) {
  const root = document.documentElement;
  const dark = settings.theme === "dark" || (settings.theme === "system" && systemDark);
  root.dataset.theme = dark ? "dark" : "light";
  root.style.colorScheme = dark ? "dark" : "light";
  const flag = (name: string, on: boolean, value: string) => {
    if (on) root.setAttribute(name, value);
    else root.removeAttribute(name);
  };
  flag("data-contrast", settings.highContrast, "high");
  flag("data-font", settings.font !== "default", settings.font);
  flag("data-spacing", settings.wideSpacing, "wide");
  flag("data-motion", settings.reduceMotion, "reduce");
  flag("data-links", settings.underlineLinks, "underline");
  flag("data-focus", settings.strongFocus, "strong");
  root.style.setProperty("--text-scale", String(settings.textScale));
  ensureFont(settings.font);
}

interface AccessibilityValue {
  settings: AccessibilitySettings;
  update: (patch: Partial<AccessibilitySettings>) => void;
  reset: () => void;
}

const AccessibilityContext = createContext<AccessibilityValue | null>(null);

export function AccessibilityProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AccessibilitySettings>(load);
  const [systemDark, setSystemDark] = useState(() => darkQuery().matches);

  useEffect(() => {
    const query = darkQuery();
    const onChange = () => setSystemDark(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  useEffect(() => apply(settings, systemDark), [settings, systemDark]);

  const update = useCallback((patch: Partial<AccessibilitySettings>) => {
    setSettings((current) => {
      const next = { ...current, ...patch };
      save(next);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    save(DEFAULT_SETTINGS);
    setSettings(DEFAULT_SETTINGS);
  }, []);

  const value = useMemo(() => ({ settings, update, reset }), [settings, update, reset]);
  return <AccessibilityContext value={value}>{children}</AccessibilityContext>;
}

export function useAccessibility() {
  const value = use(AccessibilityContext);
  if (!value) throw new Error("useAccessibility must be used inside <AccessibilityProvider>");
  return value;
}
