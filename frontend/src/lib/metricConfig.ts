export interface MetricConfigRow {
  key: string;
  label: string;
  unit: string;
  decimals: string;
  min: string;
  max: string;
  step: string;
  derived: boolean;
}

export function emptyMetricRow(): MetricConfigRow {
  return { key: "", label: "", unit: "", decimals: "1", min: "", max: "", step: "", derived: false };
}

export function metricConfigToRows(config: Record<string, unknown>): MetricConfigRow[] {
  return Object.entries(config).map(([key, raw]) => {
    const cfg = (raw ?? {}) as Record<string, unknown>;
    return {
      key,
      label: String(cfg.label ?? ""),
      unit: String(cfg.unit ?? ""),
      decimals: cfg.decimals !== undefined ? String(cfg.decimals) : "1",
      min: cfg.min !== undefined ? String(cfg.min) : "",
      max: cfg.max !== undefined ? String(cfg.max) : "",
      step: cfg.step !== undefined ? String(cfg.step) : "",
      derived: Boolean(cfg.derived),
    };
  });
}

export function rowsToMetricConfig(rows: MetricConfigRow[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const row of rows) {
    if (!row.key.trim()) continue;
    const cfg: Record<string, unknown> = { label: row.label };
    if (row.unit) cfg.unit = row.unit;
    if (row.decimals) cfg.decimals = Number(row.decimals);
    if (row.derived) {
      cfg.derived = true;
    } else {
      if (row.min) cfg.min = Number(row.min);
      if (row.max) cfg.max = Number(row.max);
      if (row.step) cfg.step = Number(row.step);
    }
    out[row.key] = cfg;
  }
  return out;
}
