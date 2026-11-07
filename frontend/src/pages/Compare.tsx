import { BackLink } from "../components/BackLink";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { PROPERTIES } from "../data/properties";
import { formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useShortlist } from "../state/shortlist";

// Illustrative comparison of the first two example properties — to be driven by the shortlist
// once per-property assessment data is available.
const COMPARED = PROPERTIES.slice(0, 2);

const ROWS: [label: string, first: string, second: string][] = [
  ["Haven match", "92% · Great fit", "78% · Good fit"],
  ["Estimated monthly cost", formatGBP(COMPARED[0].total), formatGBP(COMPARED[1].total)],
  ["Accessibility", "Step-free + lift", "6 entrance steps"],
  ["Journey to university", "22 min · 3.1 mi", "12 min · 1.2 mi"],
  ["Public transport", "Direct bus every 8 min", "Easy walk or frequent bus"],
  ["Nearby essentials", "8 within 10 min", "11 within 10 min"],
  ["Potential concerns", "2 questions", "Damp risk + access"],
  ["Energy rating", "EPC C", "EPC D"],
];

export default function Compare() {
  const { go } = useNavigation();
  const { isSaved, toggleSaved } = useShortlist();
  const best = COMPARED[0];
  const saved = isSaved(best.id);

  return (
    <main className="compare-page shell">
      <BackLink to="explore">Back to results</BackLink>
      <div className="compare-title">
        <span className="section-kicker">Your shortlist</span>
        <h1>Compare homes, side by side</h1>
        <p>See how each property stacks up against what matters to you.</p>
      </div>
      <div className="compare-table">
        <div className="compare-property blank">
          <b>Comparison</b>
        </div>
        {COMPARED.map((p) => (
          <div className="compare-property" key={p.id}>
            <img src={p.image} alt="" loading="lazy" decoding="async" />
            <span>{p.area}</span>
            <h3>{p.name}</h3>
            <b>
              {formatGBP(p.rent)}
              <small> pcm</small>
            </b>
            {p.id === best.id && <span className="best-tag">Best match</span>}
          </div>
        ))}
        {ROWS.map(([label, first, second], i) => (
          <div className="compare-row" key={label}>
            <b>{label}</b>
            <span className={i === 0 ? "highlight" : ""}>{first}</span>
            <span>{second}</span>
          </div>
        ))}
        <div className="compare-actions">
          <span />
          <Button onClick={() => toggleSaved(best.id)} aria-pressed={saved}>
            {saved ? "Saved" : "Save property"} <Icon name={saved ? "check" : "heart"} size={17} />
          </Button>
          <Button secondary onClick={() => go("property")}>
            View property
          </Button>
        </div>
      </div>
    </main>
  );
}
