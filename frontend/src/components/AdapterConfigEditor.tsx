import { isListField } from "../lib/adapterConfig";

// Structured, per-key config for most adapters (a scalar per config_schema entry —
// e.g. AC Infinity's "dev_id", Modbus's "host"/"port") since the schema itself is
// already known client-side (fetched from /api/rooms/adapters/available) — no need
// to make someone hand-write JSON for values this form already knows the shape of.
export function AdapterConfigEditor({
  schema,
  values,
  onChange,
}: {
  schema: Record<string, string>;
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
}) {
  const keys = Object.keys(schema);
  if (keys.length === 0) return null;

  return (
    <div className="field-block">
      <span className="stat-label">adapter config (device-specific)</span>
      <div className="adapter-config-editor">
        {keys.map((key) =>
          isListField(schema[key]) ? (
            <label className="field-block" key={key}>
              <span className="stat-label">
                {key} — {schema[key]}
              </span>
              <textarea
                value={values[key] ?? ""}
                onChange={(e) => onChange({ ...values, [key]: e.target.value })}
                rows={3}
              />
            </label>
          ) : (
            <label key={key}>
              {key}
              <input
                value={values[key] ?? ""}
                onChange={(e) => onChange({ ...values, [key]: e.target.value })}
                placeholder={schema[key]}
              />
              <span className="field-hint">{schema[key]}</span>
            </label>
          ),
        )}
      </div>
    </div>
  );
}
