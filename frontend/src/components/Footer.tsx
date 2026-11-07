import { useNavigation } from "../state/navigation";
import { Button } from "./Button";
import { Icon } from "./Icon";
import { Logo } from "./Logo";

export function Footer() {
  const { go } = useNavigation();
  return (
    <footer>
      <div className="shell footer-inner">
        <div>
          <Logo onClick={() => go("home")} />
          <p>
            Helping Edinburgh renters find homes
            <br />
            that fit their lives.
          </p>
        </div>
        <div>
          <b>Explore</b>
          <button type="button" onClick={() => go("explore")}>
            Properties
          </button>
          <button type="button" onClick={() => go("onboarding")}>
            How it works
          </button>
          <button type="button" onClick={() => go("screening")}>
            AI screening
          </button>
        </div>
        <div>
          <b>Haven</b>
          <button type="button" onClick={() => go("about")}>
            About us
          </button>
          <button type="button">Accessibility</button>
          <button type="button">Privacy</button>
        </div>
        <div className="footer-cta">
          <b>Ready to find your fit?</b>
          <Button onClick={() => go("onboarding")}>
            Get started <Icon name="arrow" />
          </Button>
        </div>
      </div>
      <div className="shell footer-bottom">
        <span>© {new Date().getFullYear()} Haven. Built with care in Edinburgh.</span>
        <span>Guidance, not professional advice.</span>
      </div>
    </footer>
  );
}
