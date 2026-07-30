import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { alertsApi } from "../api/alertsClient";
import type { AlertEvent, AlertRule } from "../api/alertsTypes";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { TopNav } from "../components/TopNav";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import { useRooms } from "../hooks/useRooms";
import { useRowAction } from "../hooks/useRowAction";
import { useSubmitState } from "../hooks/useSubmitState";
import { formatDateTime as formatDateTimeIso } from "../lib/formatDateTime";
import { roomLabel } from "../lib/roomLabel";
import type { Room } from "../types";

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return formatDateTimeIso(iso);
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// A rule/event stores the metric's machine key (e.g. "temp_f") since that's what's
// actually evaluated against readings — resolved back to the room's own label for
// this metric (e.g. "temp") when we can, since that's what the room's own UI calls
// it everywhere else. Falls back to the raw key for a metric no longer configured on
// that room (rules aren't retroactively cleaned up if a room's config changes).
function metricLabel(rooms: Room[], roomId: string, metricKey: string): string {
  const stat = rooms.find((r) => r.id === roomId)?.stats.find((s) => s.key === metricKey);
  return stat ? (stat.unit ? `${stat.label} (${stat.unit})` : stat.label) : metricKey;
}

function RoomLink({ rooms, roomId }: { rooms: Room[]; roomId: string }) {
  return (
    <Link to={`/rooms/${roomId}`} className="room-link">
      {roomLabel(rooms, roomId)}
    </Link>
  );
}

function ActiveAlertsTable({
  events,
  rooms,
  onAcknowledge,
  pendingId,
}: {
  events: AlertEvent[];
  rooms: Room[];
  onAcknowledge: (id: number) => void;
  pendingId: number | null;
}) {
  if (events.length === 0) return <p className="stat-label">no active alerts — everything's in range</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>room</th>
          <th>metric</th>
          <th>value</th>
          <th>threshold</th>
          <th>severity</th>
          <th>triggered</th>
          <th>status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {events.map((event) => (
          <tr key={event.id}>
            <td>
              <RoomLink rooms={rooms} roomId={event.room_id} />
            </td>
            <td>{metricLabel(rooms, event.room_id, event.metric)}</td>
            <td>{event.value.toFixed(2)}</td>
            <td>
              {event.condition === "gt" ? ">" : "<"} {event.threshold}
            </td>
            <td>
              <Badge text={event.severity} variant={event.severity === "critical" ? "danger" : "warn"} />
            </td>
            <td>{formatDateTime(event.triggered_at)}</td>
            <td>
              {event.acknowledged_at ? (
                <Badge text={`ack'd by ${event.acknowledged_by}`} variant="ok" />
              ) : (
                <Badge text="unacknowledged" variant="warn" />
              )}
            </td>
            <td>
              {!event.acknowledged_at && (
                <button
                  className="inline-button"
                  onClick={() => onAcknowledge(event.id)}
                  disabled={pendingId === event.id}
                >
                  {pendingId === event.id ? "acknowledging…" : "acknowledge"}
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function RulesTable({
  rules,
  rooms,
  onDelete,
  pendingId,
}: {
  rules: AlertRule[];
  rooms: Room[];
  onDelete: (id: string) => void;
  pendingId: string | null;
}) {
  if (rules.length === 0) return <p className="stat-label">no alert rules configured yet</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>room</th>
          <th>metric</th>
          <th>condition</th>
          <th>severity</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {rules.map((rule) => (
          <tr key={rule.id}>
            <td>
              <RoomLink rooms={rooms} roomId={rule.room_id} />
            </td>
            <td>{metricLabel(rooms, rule.room_id, rule.metric)}</td>
            <td>
              {rule.condition === "gt" ? ">" : "<"} {rule.threshold}
            </td>
            <td>
              <Badge text={rule.severity} variant={rule.severity === "critical" ? "danger" : "warn"} />
            </td>
            <td>
              <button className="inline-button" onClick={() => onDelete(rule.id)} disabled={pendingId === rule.id}>
                {pendingId === rule.id ? "removing…" : "remove"}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function CreateRuleForm({ rooms, onCreated }: { rooms: Room[]; onCreated: () => void }) {
  const [roomId, setRoomId] = useState("");
  const [metric, setMetric] = useState("");
  const [condition, setCondition] = useState<"gt" | "lt">("gt");
  const [threshold, setThreshold] = useState("");
  const [severity, setSeverity] = useState("warning");
  const { submitting, error, success, run } = useSubmitState();

  const selectedRoom = rooms.find((r) => r.id === roomId) ?? null;
  const availableMetrics = selectedRoom?.stats ?? [];

  const submit = () =>
    run(async () => {
      await alertsApi.createRule({ room_id: roomId, metric, condition, threshold: Number(threshold), severity });
      setRoomId("");
      setMetric("");
      setThreshold("");
      onCreated();
    });

  return (
    <div>
      <div className="quick-form">
        <label>
          room
          <select
            value={roomId}
            onChange={(e) => {
              setRoomId(e.target.value);
              setMetric("");
            }}
          >
            <option value="">select a room…</option>
            {rooms.map((room) => (
              <option key={room.id} value={room.id}>
                {roomLabel(rooms, room.id)}
              </option>
            ))}
          </select>
        </label>
        <label>
          metric
          <select value={metric} onChange={(e) => setMetric(e.target.value)} disabled={!roomId}>
            <option value="">
              {!roomId ? "select a room first…" : availableMetrics.length === 0 ? "no metrics on this room" : "select a metric…"}
            </option>
            {availableMetrics.map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          condition
          <select value={condition} onChange={(e) => setCondition(e.target.value as "gt" | "lt")}>
            <option value="gt">above</option>
            <option value="lt">below</option>
          </select>
        </label>
        <label>
          threshold
          <input value={threshold} onChange={(e) => setThreshold(e.target.value)} type="number" />
        </label>
        <label>
          severity
          <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="warning">warning</option>
            <option value="critical">critical</option>
          </select>
        </label>
        <button disabled={submitting || !roomId || !metric || !threshold} onClick={submit}>
          {submitting ? "adding…" : "add rule"}
        </button>
      </div>
      {success && <span className="form-success" role="status">✓ rule added</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

export function Alerts() {
  const [events, setEvents] = useState<AlertEvent[] | null>(null);
  const [rules, setRules] = useState<AlertRule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { currentOperator } = useCurrentOperator();
  const rooms = useRooms();
  const acknowledgeAction = useRowAction<number>();
  const deleteRuleAction = useRowAction<string>();

  const refresh = () => {
    alertsApi.getEvents(true).then(setEvents).catch((err) => setError(errorMessage(err)));
    alertsApi.getRules().then(setRules).catch((err) => setError(errorMessage(err)));
  };

  useEffect(refresh, []);

  const acknowledge = (id: number) =>
    acknowledgeAction.run(id, async () => {
      if (!currentOperator) return;
      await alertsApi.acknowledgeEvent(id, currentOperator.id);
      refresh();
    });

  const deleteRule = (id: string) =>
    deleteRuleAction.run(id, async () => {
      await alertsApi.deleteRule(id);
      refresh();
    });

  if (error) return <div className="page-status">Failed to load alerts: {error}</div>;

  const criticalCount = events?.filter((e) => e.severity === "critical").length ?? 0;

  return (
    <div className="page">
      <TopNav />

      <div className="section-label">Alerts</div>
      <Card>
        <div className="card-header-row">
          <h3 className="card-title">Active alerts</h3>
          {criticalCount > 0 && <Badge text={`${criticalCount} critical`} variant="danger" />}
        </div>
        <p className="card-footnote" style={{ marginTop: 12, paddingTop: 0, borderTop: "none" }}>
          Evaluated every poll cycle against each room's live readings. To be notified without
          watching this page, ask whoever manages this server to turn on a notification channel
          (webhook, email, or Discord) in its configuration.
        </p>
      </Card>

      <div className="section-label">Currently breached</div>
      <Card>
        {events ? (
          <ActiveAlertsTable events={events} rooms={rooms} onAcknowledge={acknowledge} pendingId={acknowledgeAction.pendingId} />
        ) : (
          <p className="stat-label">Loading…</p>
        )}
        {acknowledgeAction.error && <p className="form-error" role="alert">{acknowledgeAction.error}</p>}
      </Card>

      <div className="section-label">Alert rules</div>
      <Card>
        {rules ? (
          <RulesTable rules={rules} rooms={rooms} onDelete={deleteRule} pendingId={deleteRuleAction.pendingId} />
        ) : (
          <p className="stat-label">Loading…</p>
        )}
        {deleteRuleAction.error && <p className="form-error" role="alert">{deleteRuleAction.error}</p>}
        <CreateRuleForm rooms={rooms} onCreated={refresh} />
      </Card>
    </div>
  );
}
