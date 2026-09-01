import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, connectLiveUpdates } from "../api/client";
import { Card } from "../components/Card";
import { CardHeader } from "../components/CardHeader";
import { EditRoomForm } from "../components/EditRoomForm";
import { LiveConnectionNotice } from "../components/LiveConnectionNotice";
import { OperatorPicker } from "../components/OperatorPicker";
import { Sparkline } from "../components/Sparkline";
import { StatGrid } from "../components/StatGrid";
import { TopNav } from "../components/TopNav";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import { useSubmitState } from "../hooks/useSubmitState";
import { formatTime } from "../lib/formatDateTime";
import type { ReadingPoint, Room } from "../types";

export function RoomDetail() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const [room, setRoom] = useState<Room | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [readings, setReadings] = useState<ReadingPoint[]>([]);
  // Deliberately separate from the delete action's own error state below — a failed
  // *delete* must not be indistinguishable from the room's data failing to *load* in
  // the first place. They used to share one `error` field, and a failed delete (a
  // transient server error, say) would blow away the whole page — including the only
  // link back to the facility — leaving a dead end with no reachable navigation.
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [liveConnected, setLiveConnected] = useState(true);
  const { submitting: deleting, error: deleteError, run: runDelete } = useSubmitState();
  const {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();
  // Read inside the live-update handler without making the websocket effect below
  // depend on selectedMetric — otherwise switching metric tabs tore down and
  // reopened the whole connection on every click instead of just changing which
  // metric the handler cares about.
  const selectedMetricRef = useRef(selectedMetric);
  useEffect(() => {
    selectedMetricRef.current = selectedMetric;
  }, [selectedMetric]);

  const handleDelete = () =>
    runDelete(async () => {
      if (!roomId) return;
      if (!currentOperator) throw new Error("pick who you are (below) before deleting a room");
      if (!confirm(`Delete "${room?.title || roomId}"? This also removes its reading history and alert rules.`)) return;
      await api.deleteRoom(roomId, currentOperator.id);
      navigate("/");
    });

  useEffect(() => {
    if (!roomId) return;
    api
      .getRoom(roomId)
      .then((data) => {
        setRoom(data);
        setSelectedMetric(data.stats[0]?.key ?? null);
      })
      .catch((err) => setLoadError(String(err)));
  }, [roomId]);

  useEffect(() => {
    if (!roomId || !selectedMetric) return;
    api.getRoomReadings(roomId, selectedMetric).then(setReadings);
  }, [roomId, selectedMetric]);

  useEffect(() => {
    if (!roomId) return;
    const disconnect = connectLiveUpdates((msg) => {
      if (msg.room_id !== roomId) return;
      setRoom((prev) => (prev ? { ...prev, stats: msg.stats } : prev));
      const updated = msg.stats.find((s) => s.key === selectedMetricRef.current);
      if (updated) {
        setReadings((prev) => [...prev.slice(-199), { ts: new Date().toISOString(), value: updated.value }]);
      }
    }, setLiveConnected);
    return disconnect;
  }, [roomId]);

  if (loadError) return <div className="page-status">Failed to load: {loadError}</div>;
  if (!room) return <div className="page-status">Loading…</div>;

  return (
    <div className="page">
      <TopNav />
      <LiveConnectionNotice connected={liveConnected} />
      <div className="facility-header" style={{ marginBottom: 24 }}>
        <Link to="/" className="back-link" style={{ margin: 0 }}>
          ← Back to facility
        </Link>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="inline-button" onClick={() => setEditing((v) => !v)}>
              {editing ? "cancel edit" : "edit room"}
            </button>
            <button className="inline-button danger" onClick={handleDelete} disabled={deleting}>
              {deleting ? "deleting…" : "delete room"}
            </button>
          </div>
          {deleteError && <p className="form-error" role="alert" style={{ margin: 0 }}>{deleteError}</p>}
        </div>
      </div>

      <OperatorPicker
        operators={operators}
        currentOperatorId={currentOperatorId}
        onChange={changeCurrentOperator}
        onOperatorCreated={handleOperatorCreated}
        onOperatorUpdated={handleOperatorUpdated}
        onOperatorDeactivated={handleOperatorDeactivated}
      />

      {editing ? (
        <EditRoomForm
          room={room}
          currentOperator={currentOperator}
          onCancel={() => setEditing(false)}
          onUpdated={(updated) => {
            setRoom(updated);
            setSelectedMetric(updated.stats[0]?.key ?? null);
            setEditing(false);
          }}
        />
      ) : (
        <Card>
          <CardHeader subtitle={room.subtitle} title={room.title} badge={room.badge} />
          <StatGrid stats={room.stats} />
          {room.footnote && <p className="card-footnote">{room.footnote}</p>}

          {room.stats.length > 0 && (
            <>
              <div className="metric-tabs">
                {room.stats.map((stat) => (
                  <button
                    key={stat.key}
                    className={`metric-tab ${stat.key === selectedMetric ? "active" : ""}`}
                    onClick={() => setSelectedMetric(stat.key)}
                  >
                    {stat.label}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 18 }}>
                <Sparkline points={readings} />
              </div>
              <div className="history-list" tabIndex={0} role="region" aria-label="Recent readings">
                {[...readings]
                  .slice(-20)
                  .reverse()
                  .map((point) => (
                    <div className="history-row" key={point.ts}>
                      <span>{formatTime(point.ts)}</span>
                      <span className="history-value">{point.value.toFixed(2)}</span>
                    </div>
                  ))}
              </div>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
