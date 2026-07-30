// A schema entry whose description reads "list of {...}" (currently only Modbus's
// "registers", a genuinely nested list of per-register mappings) stays a labeled JSON
// textarea — collapsing that into individual fields would need a full register-map
// builder, out of scope here, but at least it's one clearly-labeled field instead of
// the whole adapter_config being an opaque blob.
export function isListField(description: string): boolean {
  return /^list of/i.test(description);
}

export function adapterConfigToValues(config: Record<string, unknown>, schema: Record<string, string>): Record<string, string> {
  const values: Record<string, string> = {};
  for (const key of Object.keys(schema)) {
    const raw = config[key];
    if (raw === undefined) {
      values[key] = "";
    } else if (isListField(schema[key]) || typeof raw === "object") {
      values[key] = JSON.stringify(raw, null, 2);
    } else {
      values[key] = String(raw);
    }
  }
  return values;
}

export function valuesToAdapterConfig(values: Record<string, string>, schema: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(values)) {
    if (!value.trim()) continue;
    if (isListField(schema[key] ?? "")) {
      out[key] = JSON.parse(value); // let a bad-JSON error surface to the caller's try/catch
    } else {
      out[key] = value;
    }
  }
  return out;
}
