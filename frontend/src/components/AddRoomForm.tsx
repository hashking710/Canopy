import { useEffect, useState } from "react";
import { api, type AdapterInfo } from "../api/client";
import type { Operator } from "../api/complianceTypes";
import { AdapterConfigEditor } from "./AdapterConfigEditor";
import { DeviceDiscoveryPanel } from "./DeviceDiscoveryPanel";
import { EnvVarNotice } from "./EnvVarNotice";
import { useSettings } from "../hooks/useSettings";
import { useSubmitState } from "../hooks/useSubmitState";
import { adapterConfigToValues, valuesToAdapterConfig } from "../lib/adapterConfig";
import { metricConfigToRows, rowsToMetricConfig, type MetricConfigRow } from "../lib/metricConfig";
import { MetricConfigEditor } from "./MetricConfigEditor";
import type { Room } from "../types";

// A sensible starting point for a brand-new room using the default "mock" adapter —
// two example metrics ready to tweak, rather than an empty list that looks broken.
const DEFAULT_METRIC_ROWS: MetricConfigRow[] = metricConfigToRows({
  temp_f: { label: "temp", unit: "°F", decimals: 1, min: 65, max: 85, step: 0.5 },
  rh_pct: { label: "RH", unit: "%", decimals: 1, min: 40, max: 70, step: 1 },
});

// Groups the adapter picker by connection type (driven by each adapter's own
// `category`, see adapters/base.py) instead of one flat list of ~16 similarly-terse
// names — someone with a Govee sensor can go straight to "Cloud account" instead of
// scanning the whole list. Order is deliberate: real-hardware categories first,
// mock/testing last since it's not what most people are looking for.
const CATEGORY_LABELS: Record<string, string> = {
  cloud: "Cloud account",
  local: "Local network",
  bluetooth: "Bluetooth",
  hardware: "Direct-attached (Pi GPIO/I2C)",
  testing: "Testing",
  other: "Other",
};
const CATEGORY_ORDER = ["cloud", "local", "bluetooth", "hardware", "testing", "other"];

function groupAdaptersByCategory(adapters: AdapterInfo[]): [string, AdapterInfo[]][] {
  const groups = new Map<string, AdapterInfo[]>();
  for (const adapter of adapters) {
    const category = adapter.category || "other";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category)!.push(adapter);
  }
  return CATEGORY_ORDER.filter((c) => groups.has(c)).map((c) => [c, groups.get(c)!]);
}

export function AddRoomForm({
  currentOperator,
  onCreated,
}: {
  currentOperator: Operator | null;
  onCreated: (room: Room) => void;
}) {
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [id, setId] = useState("");
  const [roomType, setRoomType] = useState("greenhouse");
  const [title, setTitle] = useState("");
  const [section, setSection] = useState("");
  const [adapterType, setAdapterType] = useState("mock");
  const [metricRows, setMetricRows] = useState<MetricConfigRow[]>(DEFAULT_METRIC_ROWS);
  const [adapterValues, setAdapterValues] = useState<Record<string, string>>({});
  const { submitting, error, run } = useSubmitState();
  const [open, setOpen] = useState(false);
  const { tempUnitDefault } = useSettings();

  useEffect(() => {
    if (!open) return;
    api.getAvailableAdapters().then(setAdapters).catch(() => setAdapters([]));
  }, [open]);

  const selectedAdapter = adapters.find((a) => a.adapter_type === adapterType);

  useEffect(() => {
    setAdapterValues(adapterConfigToValues({}, selectedAdapter?.config_schema ?? {}));
  }, [adapterType, selectedAdapter]);

  // Adapters with a fixed, predictable set of readings (Govee always reports
  // temp_f/rh_pct, etc.) ship a default_metric_config so picking one pre-fills the
  // metric editor instead of making the user retype exact key names from memory —
  // still just a starting point, editable/removable like any other row. Adapters
  // without one (Modbus, MQTT, BLE, mock, ...) are inherently user-defined, so
  // switching to one of those deliberately leaves whatever rows are already there
  // rather than clearing them.
  useEffect(() => {
    const defaults = selectedAdapter?.default_metric_config;
    if (defaults && Object.keys(defaults).length > 0) {
      setMetricRows(metricConfigToRows(defaults));
    }
  }, [adapterType, selectedAdapter]);

  const submit = () =>
    run(async () => {
      if (!currentOperator) throw new Error("pick who you are (above) before adding a room");
      let adapter_config: Record<string, unknown>;
      try {
        adapter_config = valuesToAdapterConfig(adapterValues, selectedAdapter?.config_schema ?? {});
      } catch (err) {
        throw new Error(`adapter config: ${err instanceof Error ? err.message : "invalid JSON"}`);
      }

      const room = await api.createRoom({
        id,
        room_type: roomType,
        title,
        section: section || null,
        adapter_type: adapterType,
        metric_config: rowsToMetricConfig(metricRows),
        adapter_config,
        operator_id: currentOperator.id,
      });
      onCreated(room);
      setId("");
      setTitle("");
      setOpen(false);
    });

  if (!open) {
    return (
      <button className="inline-button" onClick={() => setOpen(true)}>
        + add room
      </button>
    );
  }

  return (
    <div className="card">
      <div className="card-body">
        <p className="card-subtitle">New room</p>
        <div className="quick-form">
          <label>
            room id
            <input value={id} onChange={(e) => setId(e.target.value)} placeholder="e.g. greenhouse-c" />
          </label>
          <label>
            room type
            <input
              value={roomType}
              onChange={(e) => setRoomType(e.target.value)}
              placeholder="greenhouse"
              list="room-type-options"
            />
            <datalist id="room-type-options">
              <option value="greenhouse" />
              <option value="clone_room" />
              <option value="mother_room" />
              <option value="tissue_culture" />
              <option value="nutrient_room" />
              <option value="cold_room" />
              <option value="dry_cure" />
              <option value="press" />
              <option value="vault" />
            </datalist>
            <span className="field-hint">
              Must be spelled exactly like this — "greenhouse", "clone_room", and "mother_room" are what the
              facility's plant-count tally reads from, so a typo or different spelling silently drops that room
              from the count.
            </span>
          </label>
          <label>
            title
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="strain / room name" />
          </label>
          <label>
            section
            <input value={section} onChange={(e) => setSection(e.target.value)} placeholder="groups rooms on the dashboard" />
          </label>
          <label>
            sensor adapter
            <select value={adapterType} onChange={(e) => setAdapterType(e.target.value)}>
              {adapters.length === 0 && <option value="mock">mock</option>}
              {groupAdaptersByCategory(adapters).map(([category, group]) => (
                <optgroup key={category} label={CATEGORY_LABELS[category] ?? category}>
                  {group.map((a) => (
                    <option key={a.adapter_type} value={a.adapter_type}>
                      {a.plugin_name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        </div>

        {selectedAdapter && selectedAdapter.adapter_type !== "mock" && (
          <p className="stat-label" style={{ marginTop: 8 }}>
            {selectedAdapter.plugin_description}
          </p>
        )}
        {selectedAdapter && <EnvVarNotice envVars={selectedAdapter.required_env_vars} />}
        {selectedAdapter?.supports_discovery && (
          <DeviceDiscoveryPanel
            adapterType={adapterType}
            onPick={(address) => setAdapterValues({ ...adapterValues, address })}
          />
        )}

        <div className="field-block">
          {selectedAdapter && Object.keys(selectedAdapter.default_metric_config).length > 0 && (
            <p className="field-hint" style={{ marginBottom: 6 }}>
              Pre-filled for {selectedAdapter.plugin_name} — edit or remove rows as needed.
            </p>
          )}
          <MetricConfigEditor
            rows={metricRows}
            onChange={setMetricRows}
            needsRange={adapterType === "mock"}
            tempUnitDefault={tempUnitDefault}
          />
        </div>

        {selectedAdapter && (
          <AdapterConfigEditor
            schema={selectedAdapter.config_schema}
            values={adapterValues}
            onChange={setAdapterValues}
          />
        )}

        <div className="quick-form" style={{ marginTop: 14 }}>
          <button disabled={submitting || !id || !roomType} onClick={submit}>
            {submitting ? "creating…" : "create room"}
          </button>
          <button className="inline-button" onClick={() => setOpen(false)}>
            cancel
          </button>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}
