import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { complianceApi } from "../api/complianceClient";
import type {
  AuditLogEntry,
  Harvest,
  Operator,
  Package,
  PinPolicy,
  PlantBatch,
  PurchaseLimit,
  ReconciliationRow,
  StateComplianceRules,
  WasteEvent,
} from "../api/complianceTypes";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { OperatorPicker } from "../components/OperatorPicker";
import { ScanInput } from "../components/ScanInput";
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

function confidenceCaveat(confidence: StateComplianceRules["deadline_confidence"]): string {
  if (confidence === "primary_source") return "";
  if (confidence === "secondary_source") {
    return " (corroborated by secondary sources, not yet checked against the regulation text directly)";
  }
  return " (could not be verified — treat as a rough placeholder)";
}

const PURCHASE_LIMIT_UNIT_LABEL: Record<PurchaseLimit["unit"], string> = {
  grams_flower_equivalent: "g flower-equivalent",
  grams_flower: "g flower",
  grams_concentrate: "g concentrate",
  mg_thc_edible: "mg THC (edibles)",
  ounces_flower: "oz flower",
  grams_edible_product: "g edible product (by weight, not THC content)",
};

const PURCHASE_LIMIT_PERIOD_LABEL: Record<PurchaseLimit["period"], string> = {
  per_transaction: "per transaction",
  per_day: "per day",
  per_rolling_period: "per rolling period",
};

function formatPurchaseLimit(limit: PurchaseLimit): string {
  return `${limit.amount.toLocaleString()} ${PURCHASE_LIMIT_UNIT_LABEL[limit.unit]} ${PURCHASE_LIMIT_PERIOD_LABEL[limit.period]}`;
}

function RetailRulesSummary({ rules }: { rules: StateComplianceRules | null }) {
  if (!rules) return <p className="stat-label">Loading…</p>;
  const retail = rules.retail;

  return (
    <div>
      <p className="card-subtitle">
        Retail/dispensary rules for {rules.state_name} — what a customer may buy, not what a licensee may grow.
        {confidenceCaveat(retail.confidence)}
      </p>
      <div className="retail-rules-grid">
        <div>
          <span className="stat-label">Recreational</span>
          {retail.recreational_allowed ? (
            <>
              <div>{retail.recreational_min_age ? `${retail.recreational_min_age}+ only` : "no fixed age floor found"}</div>
              {retail.recreational_purchase_limits.length === 0 ? (
                <div className="stat-label">no purchase limits recorded</div>
              ) : (
                retail.recreational_purchase_limits.map((l, i) => (
                  <div key={i}>
                    {formatPurchaseLimit(l)}
                    {l.note && <div className="stat-label">{l.note}</div>}
                  </div>
                ))
              )}
            </>
          ) : (
            <div className="stat-label">not a legal market in this state</div>
          )}
        </div>
        <div>
          <span className="stat-label">Medical</span>
          {retail.medical_allowed ? (
            <>
              <div>{retail.medical_min_age ? `${retail.medical_min_age}+ (or via caregiver)` : "no fixed age floor found"}</div>
              {retail.medical_purchase_limits.length === 0 ? (
                <div className="stat-label">no purchase limits recorded</div>
              ) : (
                retail.medical_purchase_limits.map((l, i) => (
                  <div key={i}>
                    {formatPurchaseLimit(l)}
                    {l.note && <div className="stat-label">{l.note}</div>}
                  </div>
                ))
              )}
            </>
          ) : (
            <div className="stat-label">not a legal market in this state</div>
          )}
        </div>
        <div>
          <span className="stat-label">ID verification at sale</span>
          <div>
            {retail.id_verification_required === null ? "unresearched" : retail.id_verification_required ? "Required" : "Not required"}
          </div>
          {retail.id_verification_note && <div className="stat-label">{retail.id_verification_note}</div>}
        </div>
        <div>
          <span className="stat-label">POS sync to state tracking system</span>
          <div>
            {retail.pos_realtime_sync_required === null
              ? "unresearched"
              : retail.pos_realtime_sync_required
                ? "Required at/near time of sale"
                : "Not required in real time"}
          </div>
          {retail.pos_realtime_sync_note && <div className="stat-label">{retail.pos_realtime_sync_note}</div>}
        </div>
      </div>
      {retail.notes && <p className="card-footnote">{retail.notes}</p>}
    </div>
  );
}

function ComplianceStateForm({
  active,
  explicitlySet,
  availableStates,
  currentOperator,
  onChanged,
}: {
  active: StateComplianceRules | null;
  explicitlySet: boolean;
  availableStates: StateComplianceRules[];
  currentOperator: Operator | null;
  onChanged: () => void;
}) {
  const [stateCode, setStateCode] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      if (!currentOperator || !stateCode) return;
      await complianceApi.setStateRules({ state_code: stateCode, operator_id: currentOperator.id });
      setStateCode("");
      onChanged();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">
        Facility's compliance jurisdiction — which state's rules deadlines/testing requirements above are computed
        from. {explicitlySet ? "Explicitly set by an operator." : "Not yet explicitly set — using the server's default."}
      </p>
      <p className="form-error" role="note" style={{ marginBottom: 12 }}>
        This state-by-state ruleset is AI-researched from public regulatory text, not legal advice — regulations
        change and this project's own research has been wrong before (see individual field caveats above, e.g.
        "could not be verified"). Have a licensed attorney or compliance professional in your state review this
        before relying on it for real licensing or compliance decisions.
      </p>
      <div className="quick-form">
        <label>
          set to
          <select value={stateCode} onChange={(e) => setStateCode(e.target.value)}>
            <option value="">{active ? `currently ${active.state_name}` : "select a state…"}</option>
            {availableStates.map((s) => (
              <option key={s.state_code} value={s.state_code}>
                {s.state_name}
              </option>
            ))}
          </select>
        </label>
        <button disabled={submitting || !currentOperator || !stateCode} onClick={submit}>
          {submitting ? "saving…" : "set jurisdiction"}
        </button>
        {success && <span className="form-success" role="status">✓ jurisdiction updated</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

function PinPolicyForm({
  policy,
  currentOperator,
  onChanged,
}: {
  policy: PinPolicy | null;
  currentOperator: Operator | null;
  onChanged: () => void;
}) {
  const { submitting, error, success, run } = useSubmitState();

  const toggle = () =>
    run(async () => {
      if (!currentOperator || !policy) return;
      await complianceApi.setPinPolicy({ require_operator_pins: !policy.require_operator_pins, operator_id: currentOperator.id });
      onChanged();
    });

  if (!policy) return null;

  return (
    <div className="action-subsection">
      <p className="card-subtitle">
        Require every operator to have a PIN — without this, anyone with dashboard access can act under a
        PIN-less operator's name with no confirmation at all.
      </p>
      <div className="quick-form">
        <button disabled={submitting || !currentOperator} onClick={toggle}>
          {submitting ? "saving…" : policy.require_operator_pins ? "disable requirement" : "require PINs for everyone"}
        </button>
        {success && <span className="form-success" role="status">✓ updated</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      {policy.require_operator_pins && policy.operators_without_pin > 0 && (
        <p className="form-error" role="alert" style={{ marginTop: 8 }}>
          {policy.operators_without_pin} existing operator{policy.operators_without_pin === 1 ? "" : "s"} still{" "}
          {policy.operators_without_pin === 1 ? "doesn't" : "don't"} have a PIN set — give each one a PIN from the
          operator picker's "manage" menu above.
        </p>
      )}
    </div>
  );
}

function RoomLink({ rooms, roomId }: { rooms: Room[]; roomId: string }) {
  return (
    <Link to={`/rooms/${roomId}`} className="room-link">
      {roomLabel(rooms, roomId)}
    </Link>
  );
}

function ReconciliationTable({ rows, rooms }: { rows: ReconciliationRow[]; rooms: Room[] }) {
  if (rows.length === 0) return <p className="stat-label">no active plants tracked yet</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>room</th>
          <th>system count</th>
          <th>last physical count</th>
          <th>counted at</th>
          <th>status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.room_id}>
            <td>
              <RoomLink rooms={rooms} roomId={row.room_id} />
            </td>
            <td>{row.system_count}</td>
            <td>{row.last_physical_count ?? "—"}</td>
            <td>{formatDateTime(row.last_counted_at)}</td>
            <td>
              {row.last_physical_count === null ? (
                <Badge text="needs first count" variant="warn" />
              ) : row.discrepancy !== 0 ? (
                <Badge text={`discrepancy: ${row.discrepancy}`} variant="danger" />
              ) : row.stale ? (
                <Badge text="recount due" variant="warn" />
              ) : (
                <Badge text="reconciled" variant="ok" />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function WasteEventsTable({
  events,
  rooms,
  onMarkReported,
  pendingId,
}: {
  events: WasteEvent[];
  rooms: Room[];
  onMarkReported: (id: number) => void;
  pendingId: number | null;
}) {
  if (events.length === 0) return <p className="stat-label">no waste logged yet</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>room</th>
          <th>source</th>
          <th>type</th>
          <th>weight</th>
          <th>reason</th>
          <th>witness</th>
          <th>occurred</th>
          <th>reporting deadline</th>
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
            <td>
              {event.source_type} <span className="stat-label">{event.source_id}</span>
            </td>
            <td>{event.waste_type}</td>
            <td>{event.weight_g}g</td>
            <td>{event.reason ?? "—"}</td>
            <td>{event.witnessed_by ?? "—"}</td>
            <td>{formatDateTime(event.occurred_at)}</td>
            <td>{formatDateTime(event.reporting_deadline)}</td>
            <td>
              {event.reported_at ? (
                <Badge text="filed" variant="ok" />
              ) : event.overdue === null ? (
                <Badge text="deadline not tracked" variant="default" />
              ) : event.overdue ? (
                <Badge text="overdue" variant="danger" />
              ) : (
                <Badge text="pending" variant="warn" />
              )}
            </td>
            <td>
              {!event.reported_at && (
                <button
                  className="inline-button"
                  onClick={() => onMarkReported(event.id)}
                  disabled={pendingId === event.id}
                >
                  {pendingId === event.id ? "marking…" : "mark reported"}
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

function AuditLogFeed({ entries, rooms }: { entries: AuditLogEntry[]; rooms: Room[] }) {
  if (entries.length === 0) return <p className="stat-label">no audit history yet</p>;
  return (
    <div className="history-list" style={{ maxHeight: 320 }} tabIndex={0} role="region" aria-label="Audit trail">
      {entries.map((entry) => (
        <div className="history-row" key={entry.id}>
          <span>
            {formatDateTime(entry.occurred_at)} · {entry.entity_type}/{entry.entity_id} · {entry.action}
            {entry.room_id ? (
              <>
                {" · "}
                <RoomLink rooms={rooms} roomId={entry.room_id} />
              </>
            ) : (
              ""
            )}
          </span>
          <span className="history-value">{entry.actor}</span>
        </div>
      ))}
    </div>
  );
}

// Waste can be logged against an already-existing plant batch, harvest, or package —
// individual plant destruction has its own dedicated flow (see PlantsBatches.tsx's
// "destroy a plant" form, which calls /plants/{id}/destroy directly) since it also
// requires a witness/PIN sign-off tied to that specific plant record.
type WasteSourceType = "plant_batch" | "harvest" | "package";

function sourceOptionsFor(
  sourceType: WasteSourceType,
  batches: PlantBatch[],
  harvests: Harvest[],
  packages: Package[],
): { id: string; label: string }[] {
  if (sourceType === "plant_batch") {
    return batches.map((b) => ({ id: b.id, label: `${b.name} — ${b.strain} (${b.untracked_count} untracked)` }));
  }
  if (sourceType === "harvest") {
    return harvests.map((h) => ({ id: h.id, label: `${h.name} — ${h.strain} (${h.status})` }));
  }
  return packages.map((p) => ({ id: p.id, label: `${p.item_name} — ${p.id} (${p.weight_g}g)` }));
}

function LogWasteForm({
  operators,
  currentOperator,
  rooms,
  onLogged,
}: {
  operators: Operator[];
  currentOperator: Operator | null;
  rooms: Room[];
  onLogged: () => void;
}) {
  const [sourceType, setSourceType] = useState<WasteSourceType>("harvest");
  const [sourceId, setSourceId] = useState("");
  const [roomId, setRoomId] = useState("");
  const [wasteType, setWasteType] = useState("Plant Material");
  const [weightG, setWeightG] = useState("");
  const [pin, setPin] = useState("");
  const [witnessId, setWitnessId] = useState("");
  const { submitting, error, success, run } = useSubmitState();
  const weightRef = useRef<HTMLInputElement>(null);

  const [batches, setBatches] = useState<PlantBatch[]>([]);
  const [harvests, setHarvests] = useState<Harvest[]>([]);
  const [packages, setPackages] = useState<Package[]>([]);

  useEffect(() => {
    complianceApi.getPlantBatches().then(setBatches).catch(() => {});
    complianceApi.getHarvests().then(setHarvests).catch(() => {});
    complianceApi.getPackages().then(setPackages).catch(() => {});
  }, []);

  const options = useMemo(
    () => sourceOptionsFor(sourceType, batches, harvests, packages),
    [sourceType, batches, harvests, packages],
  );

  const witnessOptions = operators.filter((o) => o.id !== currentOperator?.id);

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.logWaste({
        source_type: sourceType,
        source_id: sourceId,
        room_id: roomId,
        waste_type: wasteType,
        weight_g: Number(weightG),
        operator_id: currentOperator.id,
        pin: pin || undefined,
        witness_operator_id: witnessId || undefined,
      });
      setSourceId("");
      setRoomId("");
      setWeightG("");
      setPin("");
      setWitnessId("");
      onLogged();
    });

  return (
    <div>
      <div className="scan-row">
        <ScanInput
          placeholder="Scan a plant batch/harvest/package tag…"
          onScan={(code) => {
            setSourceId(code);
            weightRef.current?.focus();
          }}
        />
        {sourceId && <span className="scan-result">Tag: {sourceId}</span>}
      </div>
      <div className="quick-form">
        <label>
          source type
          <select
            value={sourceType}
            onChange={(e) => {
              setSourceType(e.target.value as WasteSourceType);
              setSourceId("");
            }}
          >
            <option value="harvest">harvest</option>
            <option value="plant_batch">plant batch</option>
            <option value="package">package</option>
          </select>
        </label>
        <label>
          {sourceType === "plant_batch" ? "plant batch" : sourceType}
          <select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            <option value="">
              {options.length === 0 ? "no matching records yet" : `select a ${sourceType.replace("_", " ")}…`}
            </option>
            {options.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          room
          <select value={roomId} onChange={(e) => setRoomId(e.target.value)}>
            <option value="">select a room…</option>
            {rooms.map((room) => (
              <option key={room.id} value={room.id}>
                {roomLabel(rooms, room.id)}
              </option>
            ))}
          </select>
        </label>
        <label>
          waste type
          <input value={wasteType} onChange={(e) => setWasteType(e.target.value)} />
        </label>
        <label>
          weight (g)
          <input ref={weightRef} value={weightG} onChange={(e) => setWeightG(e.target.value)} type="number" min="0.01" step="0.01" />
        </label>
        {currentOperator?.has_pin && (
          <label>
            your PIN
            <input value={pin} onChange={(e) => setPin(e.target.value)} type="password" placeholder="required" />
          </label>
        )}
        <label>
          witness (optional)
          <select value={witnessId} onChange={(e) => setWitnessId(e.target.value)}>
            <option value="">none</option>
            {witnessOptions.map((op) => (
              <option key={op.id} value={op.id}>
                {op.name}
              </option>
            ))}
          </select>
        </label>
        <button disabled={submitting || !currentOperator || !sourceId || !roomId || !weightG} onClick={submit}>
          {submitting ? "logging…" : "log waste"}
        </button>
      </div>
      <p className="stat-label">
        Don't see the batch/harvest/package you're looking for? Scanning its tag above will fill this in even if it's
        not in the list yet, or{" "}
        <Link to="/plants" className="room-link">
          create it on the Plants &amp; harvest page
        </Link>
        .
      </p>
      {success && <span className="form-success" role="status">✓ waste logged</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

function PhysicalCountForm({
  currentOperator,
  rooms,
  reconciliation,
  onRecorded,
}: {
  currentOperator: Operator | null;
  rooms: Room[];
  reconciliation: ReconciliationRow[] | null;
  onRecorded: () => void;
}) {
  const [roomId, setRoomId] = useState("");
  const [countedValue, setCountedValue] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  // The whole point of this count is comparing it against what the system already
  // thinks is in the room — surfacing that number right here means a noob employee
  // doesn't have to scroll up to the reconciliation table and hold it in their head
  // while walking the room and typing in what they actually counted.
  const systemCount = reconciliation?.find((r) => r.room_id === roomId)?.system_count ?? null;

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.recordPhysicalCount({
        room_id: roomId,
        counted_value: Number(countedValue),
        operator_id: currentOperator.id,
      });
      setRoomId("");
      setCountedValue("");
      onRecorded();
    });

  return (
    <div>
      <div className="quick-form">
        <label>
          room
          <select value={roomId} onChange={(e) => setRoomId(e.target.value)}>
            <option value="">select a room…</option>
            {rooms.map((room) => (
              <option key={room.id} value={room.id}>
                {roomLabel(rooms, room.id)}
              </option>
            ))}
          </select>
          {roomId && (
            <span className="field-hint">
              system currently shows {systemCount ?? "—"} plant{systemCount === 1 ? "" : "s"} tracked here — count
              the room, then enter what you actually find below
            </span>
          )}
        </label>
        <label>
          counted value
          <input value={countedValue} onChange={(e) => setCountedValue(e.target.value)} type="number" min="0" />
        </label>
        <button disabled={submitting || !currentOperator || !roomId || countedValue === ""} onClick={submit}>
          {submitting ? "recording…" : "record count"}
        </button>
      </div>
      {success && <span className="form-success" role="status">✓ count recorded</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

export function Compliance() {
  const [reconciliation, setReconciliation] = useState<ReconciliationRow[] | null>(null);
  const [wasteEvents, setWasteEvents] = useState<WasteEvent[] | null>(null);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[] | null>(null);
  const [chainIntact, setChainIntact] = useState<boolean | null>(null);
  const [stateRules, setStateRules] = useState<StateComplianceRules | null>(null);
  const [stateExplicitlySet, setStateExplicitlySet] = useState(false);
  const [availableStates, setAvailableStates] = useState<StateComplianceRules[]>([]);
  const [pinPolicy, setPinPolicy] = useState<PinPolicy | null>(null);
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
  const rooms = useRooms();
  const markReportedAction = useRowAction<number>();
  const wasteExport = useSubmitState();
  const auditExport = useSubmitState();

  const refresh = () => {
    complianceApi.getReconciliation().then(setReconciliation).catch((err) => setError(errorMessage(err)));
    complianceApi.getWasteEvents().then(setWasteEvents).catch((err) => setError(errorMessage(err)));
    complianceApi.getAuditLog().then(setAuditLog).catch((err) => setError(errorMessage(err)));
    complianceApi.verifyAuditLog().then((r) => setChainIntact(r.intact)).catch((err) => setError(errorMessage(err)));
    complianceApi
      .getStateRules()
      .then((r) => {
        setStateRules(r.active);
        setStateExplicitlySet(r.explicitly_set);
        setAvailableStates(r.available);
      })
      .catch((err) => setError(errorMessage(err)));
    complianceApi.getPinPolicy().then(setPinPolicy).catch((err) => setError(errorMessage(err)));
  };

  useEffect(refresh, []);

  const markReported = (id: number) =>
    markReportedAction.run(id, async () => {
      if (!currentOperator) return;
      await complianceApi.markWasteReported(id, currentOperator.id);
      refresh();
    });

  if (error) return <div className="page-status">Failed to load compliance data: {error}</div>;

  const overdueCount = wasteEvents?.filter((e) => e.overdue).length ?? 0;
  const needsRecountCount = reconciliation?.filter((r) => r.last_physical_count === null || r.needs_recount).length ?? 0;

  return (
    <div className="page">
      <TopNav />

      <div className="section-label">Compliance</div>
      <Card>
        <p className="card-subtitle">Track-and-trace snapshot</p>
        <div className="card-header-row">
          <h3 className="card-title">Chain of custody</h3>
          <div style={{ display: "flex", gap: 8 }}>
            {overdueCount > 0 && <Badge text={`${overdueCount} waste reports overdue`} variant="danger" />}
            {needsRecountCount > 0 && <Badge text={`${needsRecountCount} rooms need a count`} variant="warn" />}
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
        <p className="card-footnote">
          Not synced to any state track-and-trace system (e.g. METRC) yet. Everything below is Canopy's own record.
          {stateRules && (
            <>
              {" "}
              Deadlines shown use {stateRules.state_name}'s rules{confidenceCaveat(stateRules.deadline_confidence)}.
            </>
          )}
        </p>
        <ComplianceStateForm
          active={stateRules}
          explicitlySet={stateExplicitlySet}
          availableStates={availableStates}
          currentOperator={currentOperator}
          onChanged={refresh}
        />
        <PinPolicyForm policy={pinPolicy} currentOperator={currentOperator} onChanged={refresh} />
      </Card>

      <div className="section-label">Retail compliance</div>
      <Card>
        <RetailRulesSummary rules={stateRules} />
      </Card>

      <div className="section-label">Plant count reconciliation</div>
      <Card>
        {reconciliation ? <ReconciliationTable rows={reconciliation} rooms={rooms} /> : <p className="stat-label">Loading…</p>}
        <PhysicalCountForm currentOperator={currentOperator} rooms={rooms} reconciliation={reconciliation} onRecorded={refresh} />
      </Card>

      <div className="section-label-row">
        <div className="section-label">Waste &amp; destruction log</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {wasteExport.error && <span className="form-error" role="alert" style={{ margin: 0 }}>{wasteExport.error}</span>}
          <button
            className="inline-button"
            disabled={wasteExport.submitting}
            onClick={() => wasteExport.run(() => complianceApi.exportWasteEventsCsv())}
          >
            {wasteExport.submitting ? "exporting…" : "export CSV"}
          </button>
        </div>
      </div>
      <Card>
        {wasteEvents ? (
          <WasteEventsTable
            events={wasteEvents}
            rooms={rooms}
            onMarkReported={markReported}
            pendingId={markReportedAction.pendingId}
          />
        ) : (
          <p className="stat-label">Loading…</p>
        )}
        {markReportedAction.error && <p className="form-error" role="alert">{markReportedAction.error}</p>}
        <LogWasteForm operators={operators} currentOperator={currentOperator} rooms={rooms} onLogged={refresh} />
      </Card>

      <div className="section-label-row">
        <div className="section-label">Audit trail</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {chainIntact !== null &&
            (chainIntact ? (
              <Badge text="chain intact" variant="ok" />
            ) : (
              <Badge text="tampering detected" variant="danger" />
            ))}
          {auditExport.error && <span className="form-error" role="alert" style={{ margin: 0 }}>{auditExport.error}</span>}
          <button
            className="inline-button"
            disabled={auditExport.submitting}
            onClick={() => auditExport.run(() => complianceApi.exportAuditLogCsv())}
          >
            {auditExport.submitting ? "exporting…" : "export CSV"}
          </button>
        </div>
      </div>
      <Card>
        {auditLog ? <AuditLogFeed entries={auditLog} rooms={rooms} /> : <p className="stat-label">Loading…</p>}
      </Card>
    </div>
  );
}
