import { useEffect, useState } from "react";
import { api, type LicenseStatus } from "../api/client";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { TopNav } from "../components/TopNav";
import { formatDateTime } from "../lib/formatDateTime";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function tierVariant(tier: string): "ok" | "default" {
  return tier === "corporate" ? "ok" : "default";
}

function checkinVariant(status: unknown): "ok" | "warn" | "danger" | "default" {
  if (status === "ok") return "ok";
  if (status === "over_limit" || status === "revoked") return "danger";
  if (status === "never_checked_in") return "warn";
  return "default";
}

function formatDate(value: unknown): string {
  if (typeof value !== "string") return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : formatDateTime(value);
}

function formatLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Fields already given their own dedicated treatment above the detail list.
const HANDLED_KEYS = new Set(["tier", "gate", "features_unlocked"]);

const DATE_KEYS = new Set(["expires_at", "last_successful_checkin", "issued_at"]);

export function License() {
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getLicenseStatus().then(setStatus).catch((err) => setError(errorMessage(err)));
  }, []);

  if (error) return <div className="page-status">Failed to load license status: {error}</div>;
  if (!status) return <div className="page-status">Loading…</div>;

  const featuresUnlocked = Array.isArray(status.features_unlocked)
    ? status.features_unlocked.length > 0
      ? status.features_unlocked.join(", ")
      : "none"
    : status.features_unlocked;

  const detailEntries = Object.entries(status).filter(([key, value]) => !HANDLED_KEYS.has(key) && value !== null);

  return (
    <div className="page">
      <TopNav />
      <div className="section-label">License</div>
      <Card>
        <div className="card-header-row">
          <p className="card-subtitle" style={{ margin: 0 }}>
            {status.gate}
          </p>
          <Badge text={status.tier} variant={tierVariant(status.tier)} />
        </div>
        <p className="stat-label" style={{ marginTop: 16 }}>
          Features unlocked: {featuresUnlocked}
        </p>

        {detailEntries.length > 0 && (
          <div className="history-list" style={{ marginTop: 16 }} tabIndex={0} role="region" aria-label="License details">
            {detailEntries.map(([key, value]) => (
              <div className="history-row" key={key}>
                <span>{formatLabel(key)}</span>
                {key === "last_checkin_status" ? (
                  <Badge text={String(value)} variant={checkinVariant(value)} />
                ) : (
                  <span className="history-value">
                    {DATE_KEYS.has(key) ? formatDate(value) : typeof value === "boolean" ? String(value) : String(value)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {status.tier === "unlicensed" && (
        <Card>
          <p className="card-subtitle">Get a free license</p>
          <p className="stat-label" style={{ margin: "8px 0 0" }}>
            Nothing above is gated — every feature on this device works exactly as
            shown, license or not. Registering a free license (two devices, no card
            required) is still worth doing: it gives this installation a real
            customer record, and if you ever add a third device, upgrading is a
            one-file swap instead of a fresh setup.
          </p>
          <a
            href="https://canopy.hkdev.run/checkout"
            target="_blank"
            rel="noreferrer"
            className="inline-button"
            style={{ display: "inline-block", marginTop: 12 }}
          >
            Get a free license →
          </a>
          <p className="stat-label" style={{ margin: "12px 0 0" }}>
            Once issued, save the downloaded <code>.lic</code> file somewhere this
            device can reach and point <code>CANOPY_LICENSE_FILE</code> at it (see{" "}
            <code>docker-compose.yml</code>), then restart. This page will pick it
            up automatically.
          </p>
        </Card>
      )}
    </div>
  );
}
