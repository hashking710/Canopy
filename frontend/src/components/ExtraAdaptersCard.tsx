import { useEffect, useState } from "react";
import { api, type AdapterInfo, type RoomAdapterInfo } from "../api/client";
import type { Operator } from "../api/complianceTypes";
import { AdapterConfigEditor } from "./AdapterConfigEditor";
import { Card } from "./Card";
import { DeviceDiscoveryPanel } from "./DeviceDiscoveryPanel";
import { EnvVarNotice } from "./EnvVarNotice";
import { useSubmitState } from "../hooks/useSubmitState";
import { adapterConfigToValues, valuesToAdapterConfig } from "../lib/adapterConfig";
import { CATEGORY_LABELS, groupAdaptersByCategory } from "../lib/adapterCategories";

// A room's primary adapter_type/adapter_config (set at creation, changed via
// EditRoomForm) covers exactly one sensor. This card manages any *additional*
// adapters on top of it — POST/DELETE /api/rooms/{id}/adapters — polled alongside
// the primary one and merged into the same reading each cycle (services/poller.py):
// a BLE temp/RH controller plus a separate CO2 probe in the same tent, for example.
// Built as its own always-visible card on the room detail page rather than folded
// into EditRoomForm, since "which extra sensors are attached" is ongoing room
// management, not a one-time creation-time choice the way the primary adapter is.
export function ExtraAdaptersCard({
  roomId,
  currentOperator,
}: {
  roomId: string;
  currentOperator: Operator | null;
}) {
  const [extraAdapters, setExtraAdapters] = useState<RoomAdapterInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [open, setOpen] = useState(false);
  const [adapterType, setAdapterType] = useState("");
  const [adapterValues, setAdapterValues] = useState<Record<string, string>>({});
  const { submitting, error: addError, run: runAdd } = useSubmitState();
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const refresh = () => {
    api
      .getRoomConfig(roomId)
      .then((config) => setExtraAdapters(config.extra_adapters))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  };

  useEffect(refresh, [roomId]);

  useEffect(() => {
    if (!open) return;
    api.getAvailableAdapters().then((list) => {
      setAdapters(list);
      setAdapterType((current) => current || list[0]?.adapter_type || "");
    });
  }, [open]);

  const selectedAdapter = adapters.find((a) => a.adapter_type === adapterType);

  useEffect(() => {
    setAdapterValues(adapterConfigToValues({}, selectedAdapter?.config_schema ?? {}));
  }, [adapterType, selectedAdapter]);

  const addAdapter = () =>
    runAdd(async () => {
      if (!currentOperator) throw new Error("pick who you are (above) before adding a sensor");
      if (!adapterType) throw new Error("pick a sensor type first");
      let adapter_config: Record<string, unknown>;
      try {
        adapter_config = valuesToAdapterConfig(adapterValues, selectedAdapter?.config_schema ?? {});
      } catch (err) {
        throw new Error(`adapter config: ${err instanceof Error ? err.message : "invalid JSON"}`);
      }
      await api.addRoomAdapter(roomId, { adapter_type: adapterType, adapter_config, operator_id: currentOperator.id });
      refresh();
      setOpen(false);
      setAdapterType("");
    });

  const removeAdapter = async (adapterId: number) => {
    setRemoveError(null);
    if (!currentOperator) {
      setRemoveError("pick who you are (above) before removing a sensor");
      return;
    }
    if (!confirm("Remove this sensor from the room? It stops being polled immediately.")) return;
    setRemovingId(adapterId);
    try {
      await api.removeRoomAdapter(roomId, adapterId, currentOperator.id);
      refresh();
    } catch (err) {
      setRemoveError(err instanceof Error ? err.message : String(err));
    } finally {
      setRemovingId(null);
    }
  };

  if (error) return <Card><p className="form-error" role="alert">{error}</p></Card>;

  return (
    <Card>
      <p className="card-subtitle">Additional sensors</p>
      <p className="stat-label" style={{ margin: "8px 0 16px" }}>
        This room's primary sensor is set on the room itself (see "edit room" above).
        Attach any number of extra sensors here — each is polled alongside the
        primary one and merged into this room's readings every cycle.
      </p>

      {!extraAdapters && <p className="stat-label">Loading…</p>}

      {extraAdapters && extraAdapters.length > 0 && (
        <div className="history-list" style={{ marginBottom: 16 }}>
          {extraAdapters.map((extra) => (
            <div className="history-row" key={extra.id}>
              <span>{extra.adapter_type}</span>
              <button
                className="inline-button danger"
                disabled={removingId === extra.id}
                onClick={() => removeAdapter(extra.id)}
              >
                {removingId === extra.id ? "removing…" : "remove"}
              </button>
            </div>
          ))}
        </div>
      )}
      {removeError && <p className="form-error" role="alert">{removeError}</p>}

      {extraAdapters && extraAdapters.length === 0 && !open && (
        <p className="stat-label" style={{ marginBottom: 16 }}>No extra sensors on this room yet.</p>
      )}

      {!open && (
        <button className="inline-button" onClick={() => setOpen(true)}>
          + add sensor
        </button>
      )}

      {open && (
        <div className="field-block">
          <div className="quick-form" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>
            <label>
              sensor adapter
              <select value={adapterType} onChange={(e) => setAdapterType(e.target.value)}>
                {adapters.length === 0 && <option value="">loading…</option>}
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
            <p className="stat-label" style={{ marginTop: 8 }}>{selectedAdapter.plugin_description}</p>
          )}
          {selectedAdapter && <EnvVarNotice envVars={selectedAdapter.required_env_vars} />}
          {selectedAdapter?.supports_discovery && (
            <DeviceDiscoveryPanel
              adapterType={adapterType}
              onPick={(address) => setAdapterValues({ ...adapterValues, address })}
            />
          )}
          {selectedAdapter && (
            <AdapterConfigEditor
              schema={selectedAdapter.config_schema}
              values={adapterValues}
              onChange={setAdapterValues}
            />
          )}

          <div className="quick-form" style={{ marginTop: 14 }}>
            <button disabled={submitting || !adapterType} onClick={addAdapter}>
              {submitting ? "adding…" : "add sensor"}
            </button>
            <button className="inline-button" onClick={() => setOpen(false)}>
              cancel
            </button>
          </div>
          {addError && <p className="form-error" role="alert">{addError}</p>}
        </div>
      )}
    </Card>
  );
}
