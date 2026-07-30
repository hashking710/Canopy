import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { masterApi, type RelayedAuditEntry, type SiteSummary } from "../api/masterClient";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { TopNav } from "../components/TopNav";
import { formatDateTime } from "../lib/formatDateTime";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function AuditLogFeed({ entries }: { entries: RelayedAuditEntry[] | null }) {
  if (!entries) return <p className="stat-label">Loading…</p>;
  if (entries.length === 0) {
    return (
      <p className="stat-label">
        No relayed audit events yet — this fills in once a site's devices are relaying compliance actions to each
        other over MQTT (see docs/architecture.md's audit-relay section). Each edge-agent's own database remains the
        real record; this is a durable, cross-device copy of the same stream for "show me everything, in one place."
      </p>
    );
  }
  return (
    <div className="history-list" style={{ maxHeight: 320 }} tabIndex={0} role="region" aria-label="Audit trail across all sites">
      {entries.map((entry) => (
        <div className="history-row" key={entry.id}>
          <span>
            {formatDateTime(entry.occurred_at)} · {entry.site_id}/{entry.origin_device_id} · {entry.entity_type}/
            {entry.entity_id} · {entry.action}
          </span>
          <span className="history-value">{entry.actor}</span>
        </div>
      ))}
    </div>
  );
}

export function MasterSites() {
  const [sites, setSites] = useState<SiteSummary[] | null>(null);
  const [auditLog, setAuditLog] = useState<RelayedAuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => masterApi.getSites().then(setSites).catch((err) => setError(errorMessage(err)));
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Only once getSites has actually succeeded at least once — on a single-site
    // setup with no master service reachable at all, there's no reason to also fire
    // a guaranteed-to-fail audit-log request on every load of this page.
    if (sites === null) return;
    const load = () => masterApi.getAuditLog().then(setAuditLog).catch(() => {});
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [sites === null]);

  if (error) {
    return (
      <div className="page">
        <TopNav />
        <div className="section-label">Master control panel</div>
        <Card>
          <p className="card-subtitle">This facility isn't part of a multi-site setup</p>
          <p className="stat-label" style={{ marginTop: 8 }}>
            The master control panel aggregates multiple Pis/sites under one "main
            brain" — a single-site setup (one Pi, one facility) doesn't need it. If
            you meant to chain sites together, see the "Which setup do I need?"
            section in the project README for how to bring up{" "}
            <code>mosquitto</code> + <code>master</code> alongside this dashboard.
          </p>
          <p className="stat-label" style={{ marginTop: 12, opacity: 0.7 }}>
            (Details for debugging: {error})
          </p>
        </Card>
      </div>
    );
  }
  if (!sites) return <div className="page-status">Loading…</div>;

  return (
    <div className="page">
      <TopNav />
      <div className="section-label">Master control panel</div>
      <Card>
        <p className="card-subtitle">Sites reporting in over MQTT</p>
        {sites.length === 0 ? (
          <p className="stat-label" style={{ marginTop: 16 }}>
            No sites have reported in yet
          </p>
        ) : (
          <div className="site-list">
            {sites.map((site) => (
              <Link key={site.site_id} to={`/master/${site.site_id}`} className="site-row">
                <span className="site-row-id">{site.site_id}</span>
                <span className="stat-label">{site.room_count} rooms</span>
                <Badge text={site.online ? "online" : "offline"} variant={site.online ? "ok" : "danger"} />
              </Link>
            ))}
          </div>
        )}
      </Card>

      <div className="section-label">Audit trail (all sites)</div>
      <Card>
        <p className="card-subtitle">
          A durable, cross-device record of every relayed compliance action this master instance has ever seen
        </p>
        <AuditLogFeed entries={auditLog} />
      </Card>
    </div>
  );
}
