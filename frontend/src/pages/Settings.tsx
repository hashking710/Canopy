import { useEffect, useState } from "react";
import { api, type BackupStatus } from "../api/client";
import { Card } from "../components/Card";
import { TopNav } from "../components/TopNav";
import { useSettings } from "../hooks/useSettings";
import { useSubmitState } from "../hooks/useSubmitState";
import { formatDateTime } from "../lib/formatDateTime";
import { TIMEZONE_OPTIONS } from "../lib/timezones";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function BackupsCard() {
  const [status, setStatus] = useState<BackupStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { submitting, error: runError, run } = useSubmitState();

  const refresh = () => {
    api.getBackupStatus().then(setStatus).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  };

  useEffect(refresh, []);

  const backUpNow = () =>
    run(async () => {
      await api.runBackupNow();
      refresh();
    });

  return (
    <Card>
      <p className="card-subtitle">Backups</p>
      <p className="stat-label" style={{ margin: "4px 0 12px" }}>
        A local, rotating snapshot of the database and any attached lab reports — runs automatically once a day. To
        protect against the device itself failing (not just accidental data loss), point{" "}
        <code>CANOPY_BACKUP_DIR</code> at a mounted network share or external drive. To restore one, stop the
        container and run <code>python -m canopy_agent.restore &lt;backup-file&gt;</code> — not something this page
        can do while the app is running.
      </p>
      {error && <p className="form-error" role="alert">{error}</p>}
      {!error && !status && <p className="stat-label">Loading…</p>}
      {status && (
        <p className="stat-label" style={{ margin: "0 0 12px" }}>
          {status.latest
            ? `Last backup: ${formatDateTime(status.latest.created_at)} (${formatBytes(status.latest.size_bytes)}) · ${status.count} kept`
            : "No backups yet — one will run automatically within a day, or trigger one now."}
        </p>
      )}
      <button className="inline-button" onClick={backUpNow} disabled={submitting}>
        {submitting ? "backing up…" : "back up now"}
      </button>
      {runError && <p className="form-error" role="alert">{runError}</p>}
    </Card>
  );
}

// .quick-form button's primary styling only applies inside a .quick-form wrapper —
// this toggle isn't a form, so its "selected" state is styled directly rather than
// fighting that selector's specificity with just a class name.
const selectedToggleStyle = {
  background: "var(--accent)",
  color: "var(--on-accent)",
  border: "1px solid var(--accent)",
};

export function Settings() {
  const { timezone, setTimezone, tempUnitDefault, setTempUnitDefault } = useSettings();

  return (
    <div className="page">
      <TopNav />
      <div className="section-label">Settings</div>
      <Card>
        <p className="card-subtitle">Applies on this device/browser only</p>

        <label className="field-block">
          Timezone for dates &amp; times shown across the dashboard
          <select value={timezone} onChange={(e) => setTimezone(e.target.value)} style={{ marginTop: 6 }}>
            {TIMEZONE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <div className="field-block">
          <span>Default temperature unit for new metrics</span>
          <p className="stat-label" style={{ margin: "4px 0 8px" }}>
            Only changes the placeholder hint when adding a new room metric — it
            doesn't convert any values already stored, since not every metric is a
            temperature (humidity, CO2, VPD, etc. keep whatever unit they were set up
            with).
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className={tempUnitDefault === "F" ? "" : "inline-button"}
              style={tempUnitDefault === "F" ? selectedToggleStyle : undefined}
              onClick={() => setTempUnitDefault("F")}
            >
              °F
            </button>
            <button
              className={tempUnitDefault === "C" ? "" : "inline-button"}
              style={tempUnitDefault === "C" ? selectedToggleStyle : undefined}
              onClick={() => setTempUnitDefault("C")}
            >
              °C
            </button>
          </div>
        </div>
      </Card>

      <BackupsCard />
    </div>
  );
}
