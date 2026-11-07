import { Icon, type IconName } from "./Icon";

interface FeatureCardProps {
  icon: IconName;
  title: string;
  text: string;
}

export function FeatureCard({ icon, title, text }: FeatureCardProps) {
  return (
    <article className="feature-card">
      <div className="feature-icon">
        <Icon name={icon} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      <span>
        Learn more <Icon name="arrow" size={16} />
      </span>
    </article>
  );
}
