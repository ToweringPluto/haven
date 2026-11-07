import { Button } from "../components/Button";
import { EdinburghSketch } from "../components/EdinburghSketch";
import { FeatureCard } from "../components/FeatureCard";
import { Icon, type IconName } from "../components/Icon";
import { IMAGES } from "../data/images";
import { useNavigation } from "../state/navigation";

const NEIGHBOURHOODS = [
  {
    name: "Leith",
    image: IMAGES.leith,
    alt: "Sandstone homes in Leith",
    title: "Independent, lively, by the water",
    text: "Best for good food, creative corners and an easy tram into town.",
  },
  {
    name: "Stockbridge",
    image: IMAGES.stockbridge,
    alt: "A traditional Stockbridge street",
    title: "Village feeling, city address",
    text: "Sunday markets, leafy walks and a proper neighbourhood high street.",
  },
  {
    name: "Marchmont",
    image: IMAGES.marchmont,
    alt: "Traditional Marchmont tenements",
    title: "Tenement charm and green space",
    text: "High ceilings, Meadows walks and the university close at hand.",
  },
];

const FEATURES: { icon: IconName; title: string; text: string }[] = [
  {
    icon: "wallet",
    title: "What will it really cost?",
    text: "Rent, council tax, energy and travel—laid out clearly, with no nasty surprises.",
  },
  {
    icon: "access",
    title: "Will it work for me?",
    text: "Steps, lifts, layouts and nearby routes considered around your own access needs.",
  },
  {
    icon: "train",
    title: "How will my day feel?",
    text: "Your journey to work, study and the places you visit most, from each front door.",
  },
  {
    icon: "spark",
    title: "What should I ask?",
    text: "A helpful look at photos and documents to spot gaps before you arrange a viewing.",
  },
];

export default function HomePage() {
  const { go } = useNavigation();
  return (
    <main className="editorial-home">
      <section className="editorial-hero shell">
        <div className="hero-story">
          <span className="edition-label">Edinburgh renter’s companion · Est. 2025</span>
          <h1>
            A home should feel
            <br />
            <em>right for your life.</em>
          </h1>
          <p>
            Come in, get comfortable. Haven helps you look beyond the listing and work out whether a
            place suits your budget, your body and your everyday journeys.
          </p>
          <div className="hero-actions">
            <Button onClick={() => go("onboarding")}>
              Tell us what you need <Icon name="arrow" />
            </Button>
            <button type="button" className="underlined-link" onClick={() => go("explore")}>
              Browse Edinburgh homes
            </button>
          </div>
          <div className="handwritten-note">
            No jargon. No hard sell. Just a friendly second opinion.
          </div>
        </div>
        <div className="hero-collage">
          <figure className="hero-postcard main-postcard">
            <img
              src={IMAGES.hero}
              alt="Edinburgh skyline glowing in the evening light"
              fetchPriority="high"
            />
            <figcaption>Edinburgh, looking rather lovely as usual</figcaption>
          </figure>
          <figure className="hero-postcard snug-postcard">
            <img src={IMAGES.snug} alt="A warm fireside reading corner" decoding="async" />
            <figcaption>A quiet corner to think things through</figcaption>
          </figure>
          <div className="wax-note">
            <Icon name="wallet" size={17} />
            <b>True cost</b>
            <span>not just the rent</span>
          </div>
          <EdinburghSketch />
        </div>
      </section>

      <section className="opening-note shell">
        <span className="drop-cap">“</span>
        <p>
          Finding a flat here can feel like a sprint. We’d rather it felt like a good conversation
          with someone who knows the city—and knows which questions are worth asking.
        </p>
        <span>— The idea behind Haven</span>
      </section>

      <section className="neighbourhood-stories shell">
        <div className="editorial-heading">
          <span className="section-kicker">Notes from around town</span>
          <h2>Every neighbourhood has its own rhythm.</h2>
          <p>
            Morning walks by the Water of Leith, late buses home from Old Town, a quiet close in
            Marchmont—we help you picture the life around the front door.
          </p>
        </div>
        <div className="postcard-ribbon">
          {NEIGHBOURHOODS.map((n, i) => (
            <article className="neighbourhood-postcard" key={n.name}>
              <img src={n.image} alt={n.alt} loading="lazy" decoding="async" />
              <span>
                {String(i + 1).padStart(2, "0")} / {n.name}
              </span>
              <h3>{n.title}</h3>
              <p>{n.text}</p>
            </article>
          ))}
        </div>
        <button type="button" className="sketch-link" onClick={() => go("explore")}>
          Open the neighbourhood guide <Icon name="arrow" size={17} />
        </button>
      </section>

      <section className="advice-ledger">
        <div className="shell advice-layout">
          <div className="advice-intro">
            <span className="section-kicker">The useful bits</span>
            <h2>A little more than rent and bedrooms.</h2>
            <p>We gather the details you’d scribble down after a really thorough viewing.</p>
            <EdinburghSketch />
          </div>
          <div className="advice-pages">
            {FEATURES.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </div>
      </section>

      <section className="fireside-invite shell">
        <div className="invite-photo">
          <img src={IMAGES.snug} alt="A welcoming fireside room" loading="lazy" decoding="async" />
          <span className="photo-tape" />
        </div>
        <div className="invite-copy">
          <span className="section-kicker">Start with a chat</span>
          <h2>Tell us what makes a place feel like yours.</h2>
          <p>
            Budget matters, of course. So do the steps at the door, the journey to work, a patch of
            green nearby and room for the dog. Take five minutes and we’ll keep all of it in mind.
          </p>
          <Button onClick={() => go("onboarding")}>
            Build my renter story <Icon name="arrow" />
          </Button>
          <small>You can change your answers whenever life changes.</small>
        </div>
      </section>
    </main>
  );
}
