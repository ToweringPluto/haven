import { useState } from "react";
import { useNavigation } from "../state/navigation";
import type { Page } from "../types";
import { Button } from "./Button";
import { Icon } from "./Icon";
import { LoginButton } from "./LoginButton";
import { LogoutButton } from "./LogoutButton";
import { Logo } from "./Logo";
import { UserBadge } from "./UserBadge";

// `highlight: false` links point at a page without marking it active (matches the design).
const NAV_LINKS: { label: string; page: Page; highlight: boolean }[] = [
  { label: "Home", page: "home", highlight: true },
  { label: "Explore properties", page: "explore", highlight: true },
  { label: "How it works", page: "onboarding", highlight: false },
  { label: "About", page: "about", highlight: true },
];

export function Nav() {
  const { page, go } = useNavigation();
  const [open, setOpen] = useState(false);

  const navigate = (next: Page, param?: string) => {
    go(next, param);
    setOpen(false);
  };

  return (
    <header className="nav-wrap">
      <nav className="nav shell" aria-label="Main">
        <Logo onClick={() => navigate("home")} />
        <div id="nav-links" className={`nav-links ${open ? "open" : ""}`}>
          {NAV_LINKS.map((link) => {
            const current = link.highlight && page === link.page;
            return (
              <button
                key={link.label}
                type="button"
                className={current ? "active" : ""}
                aria-current={current ? "page" : undefined}
                onClick={() => navigate(link.page)}
              >
                {link.label}
              </button>
            );
          })}
          <div className="mobile-actions">
            <button type="button" onClick={() => navigate("dashboard", "accessibility")}>
              <Icon name="access" size={18} /> Accessibility
            </button>
            <UserBadge onClick={() => navigate("dashboard")} />
            <LoginButton variant="text" />
            <LogoutButton />
            <Button onClick={() => navigate("onboarding")}>Get started</Button>
          </div>
        </div>
        <div className="nav-actions">
          <button
            type="button"
            className="a11y-nav-button"
            onClick={() => go("dashboard", "accessibility")}
            aria-label="Accessibility settings"
            title="Accessibility settings"
          >
            <Icon name="access" />
          </button>
          <UserBadge onClick={() => go("dashboard")} />
          <LoginButton variant="text" />
          <LogoutButton />
          <Button onClick={() => go("onboarding")}>Get started</Button>
        </div>
        <button
          type="button"
          className="menu-button"
          onClick={() => setOpen((o) => !o)}
          aria-label="Toggle menu"
          aria-expanded={open}
          aria-controls="nav-links"
        >
          <Icon name={open ? "x" : "menu"} />
        </button>
      </nav>
    </header>
  );
}
