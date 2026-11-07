import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { useNavigation } from "../state/navigation";

export default function About() {
  const { go } = useNavigation();
  return (
    <main>
      <section className="about-hero">
        <div className="shell">
          <span className="section-kicker">About Haven</span>
          <h1>
            Renting should come with
            <br />
            more clarity, not more risk.
          </h1>
          <p>
            We’re building a fairer way to understand whether a home truly fits—before signing on
            the dotted line.
          </p>
        </div>
      </section>
      <section className="about-story shell">
        <div>
          <span className="section-kicker">Why we exist</span>
          <h2>
            More information.
            <br />
            Better questions.
            <br />
            Confident decisions.
          </h2>
        </div>
        <div>
          <p>
            Too many renters make one of life's biggest financial decisions from a handful of photos
            and a short viewing. Important details about full costs, access and everyday
            practicality can be hard to find.
          </p>
          <p>
            Haven brings those details together and makes them personal. We don't tell you what to
            choose—we help you see the trade-offs clearly.
          </p>
          <Button onClick={() => go("onboarding")}>
            Find your fit <Icon name="arrow" />
          </Button>
        </div>
      </section>
    </main>
  );
}
