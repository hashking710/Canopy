import type { Metric } from "../types";

export function StatGrid({ stats }: { stats: Metric[] }) {
  if (stats.length === 0) return null;
  const cols = stats.length <= 2 ? "cols-2" : "";
  return (
    <div className={`stat-grid ${cols}`}>
      {stats.map((stat) => (
        <div key={stat.key}>
          <div className="stat-value">{stat.value.toFixed(stat.decimals)}</div>
          <div className="stat-label">
            {stat.label}
            {stat.unit ? ` ${stat.unit}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}
