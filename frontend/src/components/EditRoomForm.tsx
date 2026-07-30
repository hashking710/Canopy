import { useEffect, useState } from "react";
import { api, type AdapterInfo } from "../api/client";
import { AdapterConfigEditor } from "./AdapterConfigEditor";
import { EnvVarNotice } from "./EnvVarNotice";
import { useSettings } from "../hooks/useSettings";
import { useSubmitState } from "../hooks/useSubmitState";
import { adapterConfigToValues, valuesToAdapterConfig } from "../lib/adapterConfig";
import { Card } from "./Card";
import { metricConfigToRows, rowsToMetricConfig, type MetricConfigRow } from "../lib/metricConfig";
import { MetricConfigEditor } from "./MetricConfigEditor";
import type { Room } from "../types";

export function EditRoomForm({ room, onUpdated, onCancel }: { room: Room; onUpdated: (room: Room) => void; onCancel: () => void }) {
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [title, setTitle] = useState(room.title);
  const [subtitle, setSubtitle] = useState(room.subtitle);
  const [badge, setBadge] = useState(room.badge);
  const [footnote, setFootnote] = useState(room.footnote);
  const [section, setSection] = useState(room.section ?? "");
  const [adapterType, setAdapterType] = useState("mock");
  const [metricRows, setMetricRows] = useState<MetricConfigRow[]>([]);
  const [adapterValues, setAdapterValues] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const { submitting, error, run } = useSubmitState();
  const { tempUnitDefault } = useSettings();

  useEffect(() => {
    Promise.all([api.getAvailableAdapters(), api.getRoomConfig(room.id)])
      .then(([adapterList, config]) => {
        setAdapters(adapterList);
        setAdapterType(config.adapter_type);
        setMetricRows(metricConfigToRows(config.metric_config));
        const schema = adapterList.find((a) => a.adapter_type === config.adapter_type)?.config_schema ?? {};
        setAdapterValues(adapterConfigToValues(config.adapter_config, schema));
        setLoaded(true);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : String(err)));
  }, [room.id]);

  const selectedAdapter = adapters.find((a) => a.adapter_type === adapterType);

  const changeAdapterType = (next: string) => {
    setAdapterType(next);
    const schema = adapters.find((a) => a.adapter_type === next)?.config_schema ?? {};
    setAdapterValues(adapterConfigToValues({}, schema));
  };

  const submit = () =>
    run(async () => {
      let adapter_config: Record<string, unknown>;
      try {
        adapter_config = valuesToAdapterConfig(adapterValues, selectedAdapter?.config_schema ?? {});
      } catch (err) {
        throw new Error(`adapter config: ${err instanceof Error ? err.message : "invalid JSON"}`);
      }

      const updated = await api.updateRoom(room.id, {
        title,
        subtitle,
        badge,
        footnote,
        section: section || null,
        adapter_type: adapterType,
        metric_config: rowsToMetricConfig(metricRows),
        adapter_config,
      });
      onUpdated(updated);
    });

  if (loadError) return <Card><p className="form-error" role="alert">{loadError}</p></Card>;
  if (!loaded) return <Card><p className="stat-label">Loading current config…</p></Card>;

  return (
    <div className="card">
      <div className="card-body">
        <p className="card-subtitle">Edit room</p>
        <div className="quick-form">
          <label>
            title
            <input value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            subtitle
            <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} />
          </label>
          <label>
            badge
            <input value={badge} onChange={(e) => setBadge(e.target.value)} />
          </label>
          <label>
            section
            <input value={section} onChange={(e) => setSection(e.target.value)} />
          </label>
          <label>
            sensor adapter
            <select value={adapterType} onChange={(e) => changeAdapterType(e.target.value)}>
              {adapters.map((a) => (
                <option key={a.adapter_type} value={a.adapter_type}>
                  {a.plugin_name}
                </option>
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
        <label className="field-block">
          footnote
          <input value={footnote} onChange={(e) => setFootnote(e.target.value)} style={{ width: "100%" }} />
        </label>

        <div className="field-block">
          <MetricConfigEditor
            rows={metricRows}
            onChange={setMetricRows}
            needsRange={adapterType === "mock"}
            tempUnitDefault={tempUnitDefault}
          />
        </div>

        {selectedAdapter && (
          <AdapterConfigEditor schema={selectedAdapter.config_schema} values={adapterValues} onChange={setAdapterValues} />
        )}

        <div className="quick-form" style={{ marginTop: 14 }}>
          <button disabled={submitting} onClick={submit}>
            {submitting ? "saving…" : "save changes"}
          </button>
          <button className="inline-button" onClick={onCancel}>
            cancel
          </button>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}
