import { useEffect, useId, useRef } from "react";
import {
  SPEECH_RATES,
  TEXT_SCALES,
  useAccessibility,
  type AccessibilitySettings as Settings,
  type FontChoice,
  type ThemeChoice,
} from "../state/accessibility";
import { Button } from "./Button";
import { Icon } from "./Icon";

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "Match my device" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const FONTS: { value: FontChoice; label: string; hint: string }[] = [
  { value: "default", label: "Haven’s usual font", hint: "" },
  { value: "lexend", label: "Lexend", hint: "Wider letters, designed to make reading easier" },
  {
    value: "atkinson",
    label: "Atkinson Hyperlegible",
    hint: "Letters that are hard to confuse, for low vision",
  },
  { value: "opendyslexic", label: "OpenDyslexic", hint: "Weighted letters for dyslexia" },
];

const percent = (n: number) => `${Math.round(n * 100)}%`;

type Toggle = keyof Pick<
  Settings,
  "highContrast" | "wideSpacing" | "reduceMotion" | "underlineLinks" | "strongFocus"
>;

const TOGGLES: { key: Toggle; label: string; hint: string }[] = [
  {
    key: "highContrast",
    label: "High contrast",
    hint: "Stronger colours and borders. Works with light or dark.",
  },
  {
    key: "wideSpacing",
    label: "More space between lines and letters",
    hint: "Makes long text easier to follow.",
  },
  {
    key: "reduceMotion",
    label: "Reduce motion",
    hint: "Turns off animations and map fly-overs.",
  },
  { key: "underlineLinks", label: "Underline links", hint: "So links don’t rely on colour." },
  {
    key: "strongFocus",
    label: "Bold keyboard focus",
    hint: "A thick outline shows where you are when using the keyboard.",
  },
];

/**
 * Display and reading preferences, saved in this browser, in a modal that opens over any
 * page. Uses the native <dialog>: it traps focus, closes on Escape and returns focus to the
 * button that opened it.
 */
export function AccessibilityDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const id = useId();
  return (
    <dialog
      ref={ref}
      className="a11y-dialog"
      aria-labelledby={`${id}-title`}
      onClose={onClose}
      // A click on the backdrop (the dialog element itself, outside its content) closes it.
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {open && <AccessibilitySettings titleId={`${id}-title`} onClose={onClose} />}
    </dialog>
  );
}

function AccessibilitySettings({ titleId, onClose }: { titleId: string; onClose: () => void }) {
  const { settings, update, reset } = useAccessibility();
  const id = useId();

  return (
    <section className="a11y-card">
      <button type="button" className="a11y-close" onClick={onClose} aria-label="Close">
        <Icon name="x" />
      </button>
      <div className="feature-icon">
        <Icon name="access" />
      </div>
      <h2 id={titleId}>Accessibility</h2>
      <p>
        Change how Haven looks and reads. These settings are saved in this browser, so they
        work whether or not you’re signed in.
      </p>

      <fieldset className="a11y-choice">
        <legend>Colour theme</legend>
        <div className="a11y-segmented">
          {THEMES.map((t) => (
            <label key={t.value}>
              <input
                type="radio"
                name={`${id}-theme`}
                value={t.value}
                checked={settings.theme === t.value}
                onChange={() => update({ theme: t.value })}
              />
              <span>{t.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="a11y-choice">
        <legend>Text size</legend>
        <div className="a11y-segmented">
          {TEXT_SCALES.map((scale) => (
            <label key={scale}>
              <input
                type="radio"
                name={`${id}-size`}
                value={scale}
                checked={settings.textScale === scale}
                onChange={() => update({ textScale: scale })}
              />
              <span>{percent(scale)}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="a11y-choice">
        <legend>Font</legend>
        <div className="a11y-fonts">
          {FONTS.map((f) => (
            <label key={f.value} className={`a11y-font-${f.value}`}>
              <input
                type="radio"
                name={`${id}-font`}
                value={f.value}
                checked={settings.font === f.value}
                onChange={() => update({ font: f.value })}
              />
              <span>
                <b>{f.label}</b>
                {f.hint && <small>{f.hint}</small>}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="a11y-choice">
        <legend>Display and reading</legend>
        <div className="a11y-toggles">
          {TOGGLES.map((t) => (
            <label key={t.key}>
              <input
                type="checkbox"
                checked={settings[t.key]}
                onChange={(e) => update({ [t.key]: e.target.checked })}
              />
              <span>
                <b>{t.label}</b>
                <small>{t.hint}</small>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="a11y-choice">
        <legend>Read-aloud speed</legend>
        <div className="a11y-segmented">
          {SPEECH_RATES.map((rate) => (
            <label key={rate}>
              <input
                type="radio"
                name={`${id}-rate`}
                value={rate}
                checked={settings.speechRate === rate}
                onChange={() => update({ speechRate: rate })}
              />
              <span>{rate === 1 ? "Normal" : `${rate}×`}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="a11y-actions">
        <button type="button" className="text-button" onClick={reset}>
          Reset to defaults
        </button>
        <Button onClick={onClose}>Done</Button>
      </div>
    </section>
  );
}
