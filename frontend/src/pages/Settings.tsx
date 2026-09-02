import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type BackupStatus, type MenuSyncStatus, type SecretInfo } from "../api/client";
import { Card } from "../components/Card";
import { OperatorPicker } from "../components/OperatorPicker";
import { TopNav } from "../components/TopNav";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import { useSettings } from "../hooks/useSettings";
import { useSubmitState } from "../hooks/useSubmitState";
import { formatDateTime } from "../lib/formatDateTime";
import { TIMEZONE_OPTIONS } from "../lib/timezones";
import type { Operator } from "../api/complianceTypes";

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

function MenuSyncCard() {
  const [status, setStatus] = useState<MenuSyncStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();
  const { submitting, error: runError, run } = useSubmitState();

  const refresh = () => {
    api.getMenuSyncStatus().then(setStatus).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  };

  useEffect(refresh, []);

  const syncNow = () =>
    run(async () => {
      if (!currentOperator) throw new Error("pick who you are (below) before syncing");
      await api.runMenuSyncNow(currentOperator.id);
      refresh();
    });

  const activeProviderInfo = status?.available_providers.find((p) => p.type === status.active_provider);

  return (
    <Card>
      <p className="card-subtitle">POS / menu sync</p>
      <p className="stat-label" style={{ margin: "4px 0 12px" }}>
        Pushes current inventory — including genetics and THC/CBD potency, see the{" "}
        <Link to="/plants/genetics">Genetics</Link> page — to a point-of-sale or menu listing service (e.g. Weedmaps) on an
        interval. Credentials for whichever provider is active show up in the credentials card below once that
        provider is installed.
      </p>
      {error && <p className="form-error" role="alert">{error}</p>}
      {!error && !status && <p className="stat-label">Loading…</p>}
      {status && (
        <>
          <p className="stat-label" style={{ margin: "0 0 4px" }}>
            Active provider: <strong>{activeProviderInfo?.plugin_name ?? status.active_provider}</strong>
            {activeProviderInfo?.plugin_description ? ` — ${activeProviderInfo.plugin_description}` : ""}
          </p>
          <p className="stat-label" style={{ margin: "0 0 12px" }}>
            {status.last_synced_at
              ? `Last synced: ${formatDateTime(status.last_synced_at)} (${status.last_result.pushed ?? 0} pushed, ${status.last_result.skipped ?? 0} skipped)`
              : "Never synced yet."}
            {status.last_error && <span className="form-error"> — last attempt failed: {status.last_error}</span>}
          </p>
          <OperatorPicker
            operators={operators}
            currentOperatorId={currentOperatorId}
            onChange={changeCurrentOperator}
            onOperatorCreated={handleOperatorCreated}
            onOperatorUpdated={handleOperatorUpdated}
            onOperatorDeactivated={handleOperatorDeactivated}
          />
          <button className="inline-button" onClick={syncNow} disabled={submitting}>
            {submitting ? "syncing…" : "sync now"}
          </button>
          {runError && <p className="form-error" role="alert">{runError}</p>}
        </>
      )}
    </Card>
  );
}

// One row per credential (e.g. CANOPY_GOVEE_API_KEY) — its own component, not a loop
// inside CredentialsCard, so each row can call useSubmitState() once for its own
// save/clear action independently (rules of hooks: can't call a hook a variable
// number of times inside one component body, but a variable number of *component
// instances* each calling it once is exactly what this is).
function SecretRow({
  secret,
  currentOperator,
  onChange,
}: {
  secret: SecretInfo;
  currentOperator: Operator | null;
  onChange: () => void;
}) {
  const [value, setValue] = useState("");
  const [pin, setPin] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  // Credentials are facility-settings-tier sensitive — the API requires an
  // operator with role >= admin (see routers/secrets.py); a viewer/operator gets
  // a clear 403 from useSubmitState's own error display rather than the button
  // being silently disabled, since role isn't the picker's job to pre-judge.
  const save = () =>
    run(async () => {
      if (!currentOperator) throw new Error("pick who you are (below) before setting a credential");
      await api.setSecret(secret.key, value, currentOperator.id, pin || undefined);
      setValue("");
      setPin("");
      onChange();
    });

  const clear = () =>
    run(async () => {
      if (!currentOperator) throw new Error("pick who you are (below) before clearing a credential");
      await api.clearSecret(secret.key, currentOperator.id, pin || undefined);
      setPin("");
      onChange();
    });

  return (
    <div className="field-block" style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
        <code>{secret.key}</code>
        <span className={secret.is_set ? "stat-label" : "form-error"}>
          {secret.is_set ? "configured" : "needs setup"}
        </span>
      </div>
      <p className="stat-label" style={{ margin: "4px 0 8px" }}>
        {secret.description}
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={secret.is_set ? "enter a new value to replace it" : "not set"}
          style={{ flex: "1 1 240px" }}
        />
        {currentOperator?.has_pin && (
          <input
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="your PIN"
            style={{ flex: "0 1 120px" }}
          />
        )}
        <button className="inline-button" onClick={save} disabled={submitting || !value.trim()}>
          {submitting ? "saving…" : "save"}
        </button>
        {secret.set_via_dashboard && (
          <button className="inline-button" onClick={clear} disabled={submitting}>
            clear
          </button>
        )}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {success && <p className="stat-label">Saved — takes effect on the next poll cycle, no restart needed.</p>}
    </div>
  );
}

// The backend already returns secrets pre-sorted by (plugin_name, key) — see
// routers/secrets.py's list_secrets() — so grouping here is just "start a new
// section whenever plugin_name changes," no client-side re-sorting needed.
function groupByPlugin(secrets: SecretInfo[]): { pluginName: string; secrets: SecretInfo[] }[] {
  const groups: { pluginName: string; secrets: SecretInfo[] }[] = [];
  for (const secret of secrets) {
    const current = groups[groups.length - 1];
    if (current && current.pluginName === secret.plugin_name) {
      current.secrets.push(secret);
    } else {
      groups.push({ pluginName: secret.plugin_name, secrets: [secret] });
    }
  }
  return groups;
}

function CredentialsCard() {
  const [secrets, setSecrets] = useState<SecretInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();

  const refresh = () => {
    api.getSecrets().then(setSecrets).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  };

  useEffect(refresh, []);

  if (error) return <Card><p className="form-error" role="alert">{error}</p></Card>;
  if (secrets !== null && secrets.length === 0) return null; // nothing installed needs credentials

  return (
    <Card>
      <p className="card-subtitle">Sensor & sync credentials</p>
      <p className="stat-label" style={{ margin: "4px 0 12px" }}>
        Credentials every installed cloud sensor adapter or compliance-sync plugin needs — set here instead of
        editing docker-compose.yml/.env and restarting. Takes effect on the very next poll cycle. Values are
        write-only: once saved, this page never shows them back. Setting or clearing one needs an operator with
        the admin role.
      </p>
      <OperatorPicker
        operators={operators}
        currentOperatorId={currentOperatorId}
        onChange={changeCurrentOperator}
        onOperatorCreated={handleOperatorCreated}
        onOperatorUpdated={handleOperatorUpdated}
        onOperatorDeactivated={handleOperatorDeactivated}
      />
      {!secrets && <p className="stat-label">Loading…</p>}
      {secrets &&
        groupByPlugin(secrets).map((group) => (
          <div key={group.pluginName} className="field-block">
            <p className="card-subtitle" style={{ margin: "0 0 4px", fontWeight: 600 }}>
              {group.pluginName}
            </p>
            {group.secrets.map((s) => (
              <SecretRow key={s.key} secret={s} currentOperator={currentOperator} onChange={refresh} />
            ))}
          </div>
        ))}
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

      <MenuSyncCard />
      <CredentialsCard />
      <BackupsCard />
    </div>
  );
}
