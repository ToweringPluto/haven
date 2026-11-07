import { useState } from "react";
import { Button } from "../components/Button";
import { EdinburghSketch } from "../components/EdinburghSketch";
import { Icon } from "../components/Icon";
import {
  ACCESS_OPTIONS,
  AREA_OPTIONS,
  BUDGET_RANGE,
  NO_ACCESS_NEEDS,
  PRIORITY_OPTIONS,
} from "../data/onboarding";
import { formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile, type RenterProfile } from "../state/renterProfile";

type ChoiceField = "areas" | "access" | "priorities";

const STEPS = [
  { title: "What feels comfortable each month?" },
  { title: "Where would you like to live?", field: "areas", options: AREA_OPTIONS },
  { title: "What would make a home accessible?", field: "access", options: ACCESS_OPTIONS },
  { title: "What matters in your day-to-day?", field: "priorities", options: PRIORITY_OPTIONS },
  { title: "Where does your day usually take you?" },
] as const satisfies readonly { title: string; field?: ChoiceField; options?: string[] }[];

const TOTAL_STEPS = STEPS.length;

/** Toggles an option; "No specific needs" is exclusive of every other access option. */
function toggleChoice(field: ChoiceField, current: string[], option: string): string[] {
  if (current.includes(option)) return current.filter((o) => o !== option);
  if (field === "access") {
    if (option === NO_ACCESS_NEEDS) return [option];
    return [...current.filter((o) => o !== NO_ACCESS_NEEDS), option];
  }
  return [...current, option];
}

export default function Onboarding() {
  const { go } = useNavigation();
  const { profile, updateProfile } = useRenterProfile();
  const [step, setStep] = useState(1);
  const current = STEPS[step - 1];
  const isLast = step === TOTAL_STEPS;

  return (
    <main className="onboarding-page">
      <div className="onboarding shell">
        <aside className="local-welcome">
          <span className="postcard-pin" />
          <EdinburghSketch />
          <p>
            “There’s no perfect answer here. Tell us what would make everyday life feel easier.”
          </p>
          <small>— A note from the Haven team</small>
        </aside>
        <div className="progress-top">
          <button type="button" onClick={() => (step > 1 ? setStep(step - 1) : go("home"))}>
            ← Back
          </button>
          <span>
            Step {step} of {TOTAL_STEPS}
          </span>
          <div
            className="progress-track"
            role="progressbar"
            aria-valuemin={1}
            aria-valuemax={TOTAL_STEPS}
            aria-valuenow={step}
          >
            <i style={{ width: `${(step / TOTAL_STEPS) * 100}%` }} />
          </div>
        </div>
        <div className="onboarding-card">
          <span className="section-kicker">
            {isLast ? "Optional · Your daily journey" : "Your renter profile"}
          </span>
          <h1>{current.title}</h1>
          <p>
            {step === 1
              ? "We’ll use this to estimate your total monthly housing costs—not just the rent."
              : isLast
                ? "Add work, study or anywhere you travel to often. We’ll show how each home fits your usual routes."
                : "Choose all that apply. You can change these at any time."}
          </p>

          {step === 1 ? (
            <BudgetStep budget={profile.budget} onChange={(budget) => updateProfile({ budget })} />
          ) : "field" in current ? (
            <ChoiceGrid
              options={current.options}
              selected={profile[current.field]}
              onToggle={(option) =>
                updateProfile({
                  [current.field]: toggleChoice(current.field, profile[current.field], option),
                } as Partial<RenterProfile>)
              }
            />
          ) : (
            <JourneyStep
              destinations={profile.destinations}
              onChange={(destinations) => updateProfile({ destinations })}
            />
          )}

          <div className="onboarding-actions">
            <small>Your answers are private and only used to personalise your results.</small>
            <div className="onboarding-buttons">
              {isLast && (
                <button type="button" onClick={() => go("explore")}>
                  Skip for now
                </button>
              )}
              <Button onClick={() => (isLast ? go("explore") : setStep(step + 1))}>
                {isLast ? "See my matches" : "Continue"} <Icon name="arrow" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function BudgetStep({ budget, onChange }: { budget: number; onChange: (v: number) => void }) {
  return (
    <div className="budget-box">
      <label htmlFor="budget">Maximum monthly rent</label>
      <div className="budget-value">
        {formatGBP(budget)} <span>/ month</span>
      </div>
      <input
        id="budget"
        type="range"
        min={BUDGET_RANGE.min}
        max={BUDGET_RANGE.max}
        step={BUDGET_RANGE.step}
        value={budget}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className="range-labels">
        <span>{formatGBP(BUDGET_RANGE.min)}</span>
        <span>{formatGBP(BUDGET_RANGE.max)}+</span>
      </div>
      <div className="cost-note">
        <Icon name="info" size={18} />
        <span>We’ll also factor in council tax and estimated energy costs.</span>
      </div>
    </div>
  );
}

function ChoiceGrid({
  options,
  selected,
  onToggle,
}: {
  options: readonly string[];
  selected: string[];
  onToggle: (option: string) => void;
}) {
  return (
    <div className="choice-grid">
      {options.map((option) => {
        const isSelected = selected.includes(option);
        return (
          <button
            key={option}
            type="button"
            className={isSelected ? "selected" : ""}
            aria-pressed={isSelected}
            onClick={() => onToggle(option)}
          >
            <span>{isSelected && <Icon name="check" size={16} />}</span>
            {option}
          </button>
        );
      })}
    </div>
  );
}

function JourneyStep({
  destinations,
  onChange,
}: {
  destinations: string[];
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  const addDestination = () => {
    const value = draft.trim();
    if (value && !destinations.includes(value)) onChange([...destinations, value]);
    setDraft("");
  };

  return (
    <div className="journey-builder">
      <label htmlFor="destination">Workplace, university or postcode</label>
      <div className="destination-input">
        <Icon name="map" />
        <input
          id="destination"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addDestination()}
          placeholder="e.g. Royal Infirmary, EH16 4SA"
        />
        <button type="button" onClick={addDestination} disabled={!draft.trim()}>
          <Icon name="plus" size={17} /> Add
        </button>
      </div>
      <div className="destination-list">
        {destinations.map((item, index) => (
          <div key={item}>
            <span className="destination-number">{index + 1}</span>
            <span>
              <b>{item}</b>
              <small>We’ll check walking, cycling and public transport</small>
            </span>
            <button
              type="button"
              onClick={() => onChange(destinations.filter((d) => d !== item))}
              aria-label={`Remove ${item}`}
            >
              <Icon name="x" size={17} />
            </button>
          </div>
        ))}
      </div>
      <p className="journey-privacy">
        <Icon name="shield" size={17} /> Keep it broad if you prefer—an institution or postcode
        works just fine.
      </p>
    </div>
  );
}
