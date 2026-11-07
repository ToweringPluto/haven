import { BackLink } from "../components/BackLink";
import { Button } from "../components/Button";
import { Icon, type IconName } from "../components/Icon";
import { ReadAloudButton } from "../components/ReadAloudButton";
import { Status } from "../components/Status";
import { IMAGES } from "../data/images";
import { FEATURED_PROPERTY } from "../data/properties";
import { formatGBP } from "../lib/format";
import { useNavigation } from "../state/navigation";
import { useShortlist } from "../state/shortlist";
import type { StatusType } from "../types";

// Illustrative assessment for the featured property — to be replaced by real API data.
const ASSESSMENTS: { icon: IconName; title: string; detail: string; type: StatusType }[] = [
  { icon: "wallet", title: "Affordability", detail: "£91 under your total budget", type: "good" },
  { icon: "access", title: "Accessibility", detail: "Step-free entrance and lift", type: "good" },
  { icon: "map", title: "Nearby essentials", detail: "8 essentials within 10 min", type: "good" },
  {
    icon: "train",
    title: "Your daily journey",
    detail: "22 min · direct bus every 8 min",
    type: "good",
  },
  { icon: "spark", title: "AI screening", detail: "2 questions worth asking", type: "info" },
];

const COST_LINES: { label: string; note?: string; amount: number }[] = [
  { label: "Monthly rent", amount: FEATURED_PROPERTY.rent },
  { label: "Council tax", note: "Band B", amount: 142 },
  { label: "Energy estimate", note: "EPC C", amount: 86 },
  { label: "Broadband estimate", amount: 18 },
];

// Must match the recording in public/samples/first-impression.wav (played when signed out).
const FIRST_IMPRESSION =
  "Bright, calm and comfortably within budget. The lift and direct bus are real strengths. " +
  "We’d ask to see the building entrance and check the evening noise from The Shore.";

const ESTIMATED_TOTAL = COST_LINES.reduce((sum, line) => sum + line.amount, 0);

export default function PropertyDetail() {
  const { go } = useNavigation();
  const { isSaved, toggleSaved, addToCompare } = useShortlist();
  const property = FEATURED_PROPERTY;
  const saved = isSaved(property.id);

  return (
    <main className="detail-page shell">
      <BackLink to="explore">Back to results</BackLink>
      <div className="detail-gallery">
        <img src={property.image} alt={`${property.area} property`} fetchPriority="high" />
        <img
          src={IMAGES.street}
          alt="Traditional Edinburgh sandstone buildings"
          decoding="async"
        />
        <div className="gallery-placeholder">
          <Icon name="plus" />
          <span>View 8 photos</span>
        </div>
      </div>
      <div className="detail-layout">
        <div className="detail-main">
          <div className="detail-heading">
            <div>
              <span>{property.area}</span>
              <h1>{property.name}</h1>
              <p>1 bedroom · 1 bathroom · Furnished · 52 m²</p>
            </div>
            <div className="detail-price">
              <b>{formatGBP(property.rent)}</b>
              <span>per month</span>
            </div>
          </div>

          <div className="viewing-journal-note">
            <span>Our first impression</span>
            <p>{FIRST_IMPRESSION}</p>
            <ReadAloudButton text={FIRST_IMPRESSION} sampleFile="first-impression.wav" />
            <small>
              Things to notice at a viewing → water pressure · stair lighting · street noise
            </small>
          </div>

          <section className="assessment-card">
            <div className="assessment-head">
              <div className="big-score">
                {property.score}
                <span>%</span>
              </div>
              <div>
                <span className="section-kicker">A friendly second opinion</span>
                <h2>There’s a lot here that could work well.</h2>
                <p>Here’s how it lines up with the things you told us matter most.</p>
              </div>
            </div>
            <div className="assessment-grid">
              {ASSESSMENTS.map((a) => (
                <div className="assessment-item" key={a.title}>
                  <div className="feature-icon small">
                    <Icon name={a.icon} />
                  </div>
                  <div>
                    <b>{a.title}</b>
                    <Status type={a.type} />
                    <small>{a.detail}</small>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="cost-card">
            <div className="section-title">
              <div>
                <span className="section-kicker">True monthly cost</span>
                <h2>What you could pay each month</h2>
              </div>
              <b>
                {formatGBP(ESTIMATED_TOTAL)}
                <small>estimated total</small>
              </b>
            </div>
            <div className="cost-lines">
              {COST_LINES.map((line) => (
                <div key={line.label}>
                  <span>
                    {line.label} {line.note && <small>{line.note}</small>}
                  </span>
                  <b>{formatGBP(line.amount)}</b>
                </div>
              ))}
            </div>
            <p>
              <Icon name="info" size={17} /> Estimates are based on public data and typical usage.
              Your actual costs may vary.
            </p>
          </section>

          <section className="screening-teaser">
            <div className="feature-icon">
              <Icon name="spark" />
            </div>
            <div>
              <span className="section-kicker">AI property screening</span>
              <h2>Look closer before you view</h2>
              <p>
                Upload the listing documents or your viewing photos and Haven will help flag visible
                concerns and missing details.
              </p>
            </div>
            <Button secondary onClick={() => go("screening")}>
              Start screening <Icon name="arrow" />
            </Button>
          </section>
        </div>

        <aside className="sticky-card">
          <span>Interested in this home?</span>
          <Button onClick={() => toggleSaved(property.id)} aria-pressed={saved}>
            <Icon name={saved ? "check" : "heart"} size={18} />
            {saved ? "Saved to dashboard" : "Save property"}
          </Button>
          <Button
            secondary
            onClick={() => {
              addToCompare(property.id);
              go("compare");
            }}
          >
            Add to comparison
          </Button>
          <small>Listed 2 days ago · Ref. HVN-2841</small>
          <div className="safe-note">
            <Icon name="shield" />
            <p>
              <b>Rent safely</b>Never transfer money before viewing and verifying the property.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
