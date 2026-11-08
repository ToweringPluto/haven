import { useRef, useState } from "react";
import { useNavigation } from "../state/navigation";
import type { Page } from "../types";
import { AccessibilityDialog } from "./AccessibilitySettings";
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const cogRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);

  const navigate = (next: Page) => {
    go(next);
    setOpen(false);
  };
  const openSettings = () => {
    setOpen(false);
    setSettingsOpen(true);
  };
  // Back to whichever opener is on screen: the cog on desktop, the menu button on phones.
  const closeSettings = () => {
    setSettingsOpen(false);
    const cog = cogRef.current;
    (cog && cog.offsetParent !== null ? cog : menuRef.current)?.focus();
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
            <button type="button" onClick={openSettings} aria-haspopup="dialog">
              <Icon name="cog" size={18} /> Accessibility settings
            </button>
            <UserBadge onClick={() => navigate("dashboard")} />
            <LoginButton variant="text" />
            <LogoutButton />
            <Button onClick={() => navigate("onboarding")}>Get started</Button>
          </div>
        </div>
        <div className="nav-actions">
          <UserBadge onClick={() => go("dashboard")} />
          <LoginButton variant="text" />
          <LogoutButton />
          <Button onClick={() => go("onboarding")}>Get started</Button>
          <button
            type="button"
            ref={cogRef}
            className="a11y-nav-button"
            onClick={openSettings}
            aria-haspopup="dialog"
            aria-label="Accessibility settings"
            title="Accessibility settings"
          >
            <Icon name="cog" />
          </button>
        </div>
        <button
          type="button"
          ref={menuRef}
          className="menu-button"
          onClick={() => setOpen((o) => !o)}
          aria-label="Toggle menu"
          aria-expanded={open}
          aria-controls="nav-links"
        >
          <Icon name={open ? "x" : "menu"} />
        </button>
      </nav>
      <AccessibilityDialog open={settingsOpen} onClose={closeSettings} />
    </header>
  );
}
