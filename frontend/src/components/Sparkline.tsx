import type { ReadingPoint } from "../types";

export function Sparkline({ points }: { points: ReadingPoint[] }) {
  if (points.length < 2) return <div className="stat-label">not enough history yet</div>;

  const width = 600;
  const height = 90;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((p.value - min) / span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const areaPoints = `0,${height} ${coords.join(" ")} ${width},${height}`;
  const [lastX, lastY] = coords[coords.length - 1].split(",").map(Number);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
      <polygon points={areaPoints} fill="var(--accent-soft)" />
      <polyline points={coords.join(" ")} fill="none" stroke="var(--accent)" strokeWidth={1.75} vectorEffect="non-scaling-stroke" />
      <circle cx={lastX} cy={lastY} r={3.5} fill="var(--accent)" />
    </svg>
  );
}
