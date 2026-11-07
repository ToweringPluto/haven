import { Icon } from "./Icon";

export function Logo({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="logo" onClick={onClick} aria-label="Haven home">
      <span className="logo-mark">
        <Icon name="home" size={19} />
      </span>
      <span>
        haven<span className="logo-dot">.</span>
      </span>
    </button>
  );
}
