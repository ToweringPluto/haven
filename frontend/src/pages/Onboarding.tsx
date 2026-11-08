import { useState } from "react";
import { useEnumLabel, useEnumValues } from "../api/enums";
import { Button } from "../components/Button";
import { EdinburghSketch } from "../components/EdinburghSketch";
import { Icon } from "../components/Icon";
import {
  ACCESS_OPTIONS,
  AREA_OPTIONS,
  BUDGET_RANGE,
  DESTINATIONS,
  PERSONAS,
  PRIORITY_OPTIONS,
  type AccessKey,
} from "../data/onboarding";
import { formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useRenterProfile } from "../state/renterProfile";

const STEPS = [
  {
    title: "What feels comfortable each month?",
    intro: "We’ll compare each home’s estimated total monthly cost, not just the rent, with this.",
  },
  {
    title: "Where would you like to live?",
    intro: "Homes in these areas are listed first. Choose as many as you like, or none.",
  },
  {
    title: "Does a home need to meet any access requirements?",
    intro: "Haven checks each listing against these and tells you what it can’t confirm.",
  },
  {
    title: "What matters most to you?",
    intro: "Checks about these come first in each assessment. Nothing is turned into a score.",
  },
  {
    title: "Where does your day usually take you?",
    intro: "Optional. Pick the places you travel to most often.",
  },
] as const;

const TOTAL_STEPS = STEPS.length;

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

/** "No specific needs" is exclusive of every other access option. */
function toggleAccess(current: AccessKey[], key: AccessKey): AccessKey[] {
  if (key === "none") return current.includes("none") ? [] : ["none"];
  return toggle(
    current.filter((k) => k !== "none"),
    key,
  );
}

export default function Onboarding() {
  const { go } = useNavigation();
  const label = useEnumLabel();
  const priorityOptions = useEnumValues("priority", PRIORITY_OPTIONS);
  const { draft, updateDraft, saved, saveProfile, choosePersona } = useRenterProfile();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = STEPS[step - 1];
  const isLast = step === TOTAL_STEPS;
  const back = () => (step > 1 ? setStep(step - 1) : go(saved ? "explore" : "home"));
  const backLabel = step > 1 ? "Back" : saved ? "Back to homes" : "Back to home";

  const finish = async () => {
    setBusy(true);
    const problem = await saveProfile();
    setBusy(false);
    if (problem) setError(`We couldn’t save your profile: ${problem}`);
    else go("explore");
  };

  const pickPersona = async (id: string) => {
    setBusy(true);
    const problem = await choosePersona(id);
    setBusy(false);
    if (problem) setError(problem);
    else go("explore");
  };

  return (
    <main className="onboarding-page">
      <div className="onboarding shell">
        <aside className="local-welcome">
          <span className="postcard-pin" />
          <EdinburghSketch />
          <p>“Just looking? Explore as an example renter and see a full assessment.”</p>
          <div className="persona-picks">
            {PERSONAS.map((p) => (
              <button key={p.id} type="button" onClick={() => pickPersona(p.id)} disabled={busy}>
                <b>{p.name}</b>
                <small>{p.blurb}</small>
              </button>
            ))}
          </div>
          <small>Examples, not real people.</small>
        </aside>
        <div className="progress-top">
          <button type="button" className="back-link onboarding-back" onClick={back}>
            ← {backLabel}
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
          <p>{current.intro}</p>

          {step === 1 && (
            <div className="budget-box">
              <label htmlFor="budget">Maximum total monthly housing cost</label>
              <div className="budget-value">
                {formatGBP(draft.budget)} <span>/ month</span>
              </div>
              <input
                id="budget"
                type="range"
                min={BUDGET_RANGE.min}
                max={BUDGET_RANGE.max}
                step={BUDGET_RANGE.step}
                value={draft.budget}
                onChange={(e) => updateDraft({ budget: Number(e.target.value) })}
              />
              <div className="range-labels">
                <span>{formatGBP(BUDGET_RANGE.min)}</span>
                <span>{formatGBP(BUDGET_RANGE.max)}</span>
              </div>
              <div className="cost-note">
                <Icon name="info" size={18} />
                <span>Includes rent, council tax and estimated energy costs.</span>
              </div>
            </div>
          )}

          {step === 2 && (
            <ChoiceGrid
              options={AREA_OPTIONS.map((a) => ({ value: a, label: a }))}
              selected={draft.areas}
              onToggle={(a) => updateDraft({ areas: toggle(draft.areas, a) })}
            />
          )}

          {step === 3 && (
            <ChoiceGrid
              options={ACCESS_OPTIONS.map((o) => ({ value: o.key, label: o.label }))}
              selected={draft.access}
              onToggle={(k) => updateDraft({ access: toggleAccess(draft.access, k as AccessKey) })}
            />
          )}

          {step === 4 && (
            <ChoiceGrid
              options={priorityOptions.map((p) => ({ value: p, label: label("priority", p) }))}
              selected={draft.priorities}
              onToggle={(p) => updateDraft({ priorities: toggle(draft.priorities, p) })}
            />
          )}

          {step === 5 && (
            <div className="journey-builder">
              <ChoiceGrid
                options={DESTINATIONS.map((d) => ({ value: d.id, label: d.name }))}
                selected={draft.destinationIds}
                onToggle={(id) => updateDraft({ destinationIds: toggle(draft.destinationIds, id) })}
              />
              <label htmlFor="max-travel">Longest journey you’d be happy with</label>
              <select
                id="max-travel"
                value={draft.maxTravelMinutes}
                onChange={(e) => updateDraft({ maxTravelMinutes: Number(e.target.value) })}
              >
                {[20, 30, 40, 50, 60].map((m) => (
                  <option key={m} value={m}>
                    {m} minutes
                  </option>
                ))}
              </select>
              <p className="journey-privacy">
                <Icon name="shield" size={17} /> Your answers are only used to assess homes for you.
              </p>
            </div>
          )}

          {error && (
            <p className="screen-notice" role="alert">
              {error}
            </p>
          )}

          <div className="onboarding-actions">
            <small>You can change these at any time.</small>
            <div className="onboarding-buttons">
              <Button secondary onClick={back} disabled={busy}>
                {backLabel}
              </Button>
              <Button
                onClick={() => (isLast ? finish() : setStep(step + 1))}
                disabled={busy}
              >
                {isLast ? (busy ? "Saving…" : "See homes for me") : "Continue"}{" "}
                <Icon name="arrow" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function ChoiceGrid({
  options,
  selected,
  onToggle,
}: {
  options: { value: string; label: string }[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div className="choice-grid">
      {options.map((option) => {
        const isSelected = selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            className={isSelected ? "selected" : ""}
            aria-pressed={isSelected}
            onClick={() => onToggle(option.value)}
          >
            <span>{isSelected && <Icon name="check" size={16} />}</span>
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
