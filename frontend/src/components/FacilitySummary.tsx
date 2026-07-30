import type { Room } from "../types";
import { Badge } from "./Badge";
import { Card } from "./Card";

export function FacilitySummary({ facility }: { facility: Room }) {
  return (
    <Card>
      <div className="facility-header">
        <div>
          <p className="card-subtitle" style={{ margin: 0 }}>
            {facility.subtitle}
          </p>
        </div>
        <div className="facility-badge-row">
          <Badge text={facility.badge} />
        </div>
      </div>

      <div className="kpi-strip">
        {facility.stats.map((stat) => (
          <div className="kpi" key={stat.key}>
            <div className="kpi-value">{stat.value.toFixed(stat.decimals)}</div>
            <div className="kpi-label">
              {stat.label}
              {stat.unit ? ` ${stat.unit}` : ""}
            </div>
          </div>
        ))}
      </div>

      {facility.footnote && <p className="facility-footnote">{facility.footnote}</p>}
    </Card>
  );
}
