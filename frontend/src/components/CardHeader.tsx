import { Badge } from "./Badge";

export function CardHeader({ subtitle, title, badge }: { subtitle: string; title: string; badge: string }) {
  if (title) {
    return (
      <>
        <p className="card-subtitle">{subtitle}</p>
        <div className="card-header-row">
          <h3 className="card-title">{title}</h3>
          <Badge text={badge} />
        </div>
      </>
    );
  }
  return (
    <div className="card-header-row">
      <p className="card-subtitle" style={{ margin: 0 }}>
        {subtitle}
      </p>
      <Badge text={badge} />
    </div>
  );
}
