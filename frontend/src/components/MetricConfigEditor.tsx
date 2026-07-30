import { emptyMetricRow, type MetricConfigRow } from "../lib/metricConfig";

// Each metric a room displays (e.g. "temp_f" -> temp °F, 65-85 range) used to be a
// hand-edited JSON blob. This renders the same shape as a table of plain fields —
// min/max/step are what the mock adapter walks a random value within for local dev;
// a real adapter reads hardware instead and only needs label/unit/decimals, hence
// the "derived" escape hatch (e.g. VPD, computed from temp+RH, not sensed directly).
export function MetricConfigEditor({
  rows,
  onChange,
  needsRange,
  tempUnitDefault = "F",
}: {
  rows: MetricConfigRow[];
  onChange: (rows: MetricConfigRow[]) => void;
  needsRange: boolean;
  // Only changes the unit input's placeholder hint — never auto-fills a value,
  // since most metrics (humidity, CO2, VPD) aren't temperature at all and a
  // filled-in "°F" would just be wrong for them.
  tempUnitDefault?: "F" | "C";
}) {
  const unitPlaceholder = `unit (e.g. °${tempUnitDefault})`;
  const update = (index: number, patch: Partial<MetricConfigRow>) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };
  const remove = (index: number) => onChange(rows.filter((_, i) => i !== index));
  const add = () => onChange([...rows, emptyMetricRow()]);

  return (
    <div className="metric-config-editor">
      <span className="stat-label">metrics this room displays</span>
      {rows.length === 0 && <p className="stat-label">no metrics configured yet</p>}
      {rows.length > 0 && (
        <p className="field-hint" style={{ maxWidth: "none" }}>
          "derived" = computed from other metrics rather than read from a sensor (e.g. VPD, calculated from temp +
          RH) — check it for a metric like that and it'll skip the min/max/step range below, since nothing walks a
          random value for it.
        </p>
      )}
      {rows.map((row, i) => (
        <div className="metric-config-row" key={i}>
          <input
            value={row.key}
            onChange={(e) => update(i, { key: e.target.value })}
            placeholder="key (e.g. temp_f)"
          />
          <input value={row.label} onChange={(e) => update(i, { label: e.target.value })} placeholder="label (e.g. temp)" />
          <input value={row.unit} onChange={(e) => update(i, { unit: e.target.value })} placeholder={unitPlaceholder} />
          <input
            value={row.decimals}
            onChange={(e) => update(i, { decimals: e.target.value })}
            type="number"
            placeholder="decimals"
          />
          <label
            className="metric-config-derived"
            title="Computed from other metrics rather than read from a sensor (e.g. VPD, calculated from temp + RH) — skips the min/max/step range since nothing walks a random value for it."
          >
            <input type="checkbox" checked={row.derived} onChange={(e) => update(i, { derived: e.target.checked })} />
            derived
          </label>
          {!row.derived && (
            <>
              <input
                value={row.min}
                onChange={(e) => update(i, { min: e.target.value })}
                type="number"
                placeholder={needsRange ? "min (required)" : "min"}
              />
              <input
                value={row.max}
                onChange={(e) => update(i, { max: e.target.value })}
                type="number"
                placeholder={needsRange ? "max (required)" : "max"}
              />
              <input value={row.step} onChange={(e) => update(i, { step: e.target.value })} type="number" placeholder="step" />
            </>
          )}
          <button type="button" className="inline-button" onClick={() => remove(i)}>
            remove
          </button>
        </div>
      ))}
      <button type="button" className="inline-button" onClick={add}>
        + add metric
      </button>
    </div>
  );
}
