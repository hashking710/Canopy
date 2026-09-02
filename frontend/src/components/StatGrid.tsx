import type { Metric } from "../types";

// A room's metric_config is entirely user-defined (anywhere from 1 to 6+ metrics),
// so a fixed column count orphans a lone cell on its own row whenever the count
// isn't a clean multiple of it (a real, common case here — 4 metrics in a naive
// fixed-3 grid renders 3, then 1 by itself). Chooses the count that keeps every
// row balanced (2+ items) instead: exact-match up to 3, 2x2 for 4, otherwise 3
// unless that would leave a single orphan (count % 3 === 1), in which case 4
// (e.g. 7 -> 4+3, not 3+3+1).
function columnsFor(count: number): number {
  if (count <= 3) return Math.max(count, 1);
  if (count === 4) return 2;
  return count % 3 === 1 ? 4 : 3;
}

export function StatGrid({ stats }: { stats: Metric[] }) {
  if (stats.length === 0) return null;
  return (
    <div className="stat-grid" style={{ gridTemplateColumns: `repeat(${columnsFor(stats.length)}, minmax(0, 1fr))` }}>
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
