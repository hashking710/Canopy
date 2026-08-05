import { useState } from "react";
import { api, type DiscoveredDevice } from "../api/client";
import { useSubmitState } from "../hooks/useSubmitState";

// Shown only for adapters whose supports_discovery flag is true (BLE-family
// adapters today — see SensorAdapter.supports_discovery's docstring for why
// cloud/local-network adapters can't offer this the same way under Docker's
// default bridge networking). Saves whoever's setting up a room from needing an
// external BLE scanner app just to find a device's MAC address.
export function DeviceDiscoveryPanel({
  adapterType,
  onPick,
}: {
  adapterType: string;
  onPick: (address: string) => void;
}) {
  const [devices, setDevices] = useState<DiscoveredDevice[] | null>(null);
  const { submitting, error, run } = useSubmitState();

  const scan = () =>
    run(async () => {
      setDevices(await api.discoverAdapterDevices(adapterType));
    });

  return (
    <div className="field-block">
      <button type="button" className="inline-button" onClick={scan} disabled={submitting}>
        {submitting ? "scanning… (up to 15s)" : "scan for nearby devices"}
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
      {devices && devices.length === 0 && (
        <p className="stat-label" style={{ margin: "6px 0 0" }}>
          No devices found nearby — make sure it's powered on and in range, then try again.
        </p>
      )}
      {devices && devices.length > 0 && (
        <ul style={{ margin: "8px 0 0", paddingLeft: 0, listStyle: "none" }}>
          {devices.map((d) => (
            <li
              key={d.address}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "4px 0" }}
            >
              <span>
                <strong>{d.name || "(unnamed device)"}</strong> <code>{d.address}</code>
                {typeof d.rssi === "number" && <span className="stat-label"> · {d.rssi} dBm</span>}
              </span>
              <button type="button" className="inline-button" onClick={() => onPick(d.address)}>
                use this
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
