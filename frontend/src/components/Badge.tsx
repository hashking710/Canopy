type Variant = "default" | "ok" | "warn" | "danger";

export function Badge({ text, variant = "default" }: { text: string; variant?: Variant }) {
  if (!text) return null;
  const variantClass = variant === "default" ? "" : `badge-${variant}`;
  return <span className={`badge ${variantClass}`}>{text}</span>;
}
