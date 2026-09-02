import { useEffect, useState } from "react";
import { complianceApi } from "../api/complianceClient";
import type { Harvest, HarvestWeightLog, Operator } from "../api/complianceTypes";
import { strainsApi } from "../api/strainsClient";
import type { Strain } from "../api/strainsTypes";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { OperatorPicker } from "../components/OperatorPicker";
import { PlantsSubNav } from "../components/PlantsSubNav";
import { TopNav } from "../components/TopNav";
import { RoomSelect } from "../components/RoomSelect";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import { useRooms } from "../hooks/useRooms";
import { useSubmitState } from "../hooks/useSubmitState";
import { formatDate, formatDateTime } from "../lib/formatDateTime";
import { roomLabel } from "../lib/roomLabel";
import type { Room } from "../types";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function HarvestsTable({ harvests, rooms }: { harvests: Harvest[]; rooms: Room[] }) {
  if (harvests.length === 0) return <p className="stat-label">no harvests yet</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>name</th>
          <th>strain</th>
          <th>source room</th>
          <th>drying room</th>
          <th>wet weight</th>
          <th>started</th>
          <th>finished</th>
          <th>status</th>
        </tr>
      </thead>
      <tbody>
        {harvests.map((h) => (
          <tr key={h.id}>
            <td>{h.name}</td>
            <td>{h.strain}</td>
            <td>{roomLabel(rooms, h.source_room_id)}</td>
            <td>{roomLabel(rooms, h.drying_room_id)}</td>
            <td>{h.wet_weight_g}g</td>
            <td>{formatDate(h.started_at)}</td>
            <td>{h.finished_at ? formatDate(h.finished_at) : "—"}</td>
            <td>
              <Badge text={h.status} variant={h.status === "active" ? "ok" : "default"} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function CreateHarvestForm({
  rooms,
  strains,
  currentOperator,
  onCreated,
}: {
  rooms: Room[];
  strains: Strain[];
  currentOperator: Operator | null;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [strain, setStrain] = useState("");
  const [strainId, setStrainId] = useState("");
  const [sourceRoomId, setSourceRoomId] = useState("");
  const [dryingRoomId, setDryingRoomId] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  // See PlantsBatches.tsx's CreateBatchForm for why this is additive, not a
  // replacement for the free-text field.
  const pickRegistryStrain = (id: string) => {
    setStrainId(id);
    const picked = strains.find((s) => s.id === id);
    if (picked) setStrain(picked.name);
  };

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.createHarvest({
        name,
        strain,
        strain_id: strainId || null,
        source_room_id: sourceRoomId,
        drying_room_id: dryingRoomId || undefined,
        operator_id: currentOperator.id,
      });
      setName("");
      setStrain("");
      setStrainId("");
      setSourceRoomId("");
      setDryingRoomId("");
      onCreated();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">Start a new harvest</p>
      <div className="quick-form">
        <label>
          harvest name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="must be unique" />
        </label>
        {strains.length > 0 && (
          <label>
            from registry (optional)
            <select value={strainId} onChange={(e) => pickRegistryStrain(e.target.value)}>
              <option value="">type strain manually…</option>
              {strains.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          strain
          <input
            value={strain}
            onChange={(e) => {
              setStrain(e.target.value);
              setStrainId("");
            }}
          />
        </label>
        <label>
          source room
          <RoomSelect rooms={rooms} value={sourceRoomId} onChange={setSourceRoomId} />
        </label>
        <label>
          drying room (optional)
          <RoomSelect rooms={rooms} value={dryingRoomId} onChange={setDryingRoomId} allowNone="none yet" />
        </label>
        <button disabled={submitting || !currentOperator || !name || !strain || !sourceRoomId} onClick={submit}>
          {submitting ? "starting…" : "start harvest"}
        </button>
        {success && <span className="form-success" role="status">✓ harvest started</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

function WeighHarvestForm({
  harvests,
  rooms,
  currentOperator,
  onDone,
}: {
  harvests: Harvest[];
  rooms: Room[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const [harvestId, setHarvestId] = useState("");
  const [stage, setStage] = useState<"wet" | "dry" | "cure">("dry");
  const [weightG, setWeightG] = useState("");
  const [roomId, setRoomId] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.weighHarvest(harvestId, {
        stage,
        weight_g: Number(weightG),
        room_id: roomId,
        operator_id: currentOperator.id,
      });
      setWeightG("");
      onDone();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">Log a weigh-in (wet / dry / cure)</p>
      <div className="quick-form">
        <label>
          harvest
          <select value={harvestId} onChange={(e) => setHarvestId(e.target.value)}>
            <option value="">{harvests.length === 0 ? "no harvests yet" : "select a harvest…"}</option>
            {harvests.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name} — {h.strain}
              </option>
            ))}
          </select>
        </label>
        <label>
          stage
          <select value={stage} onChange={(e) => setStage(e.target.value as "wet" | "dry" | "cure")}>
            <option value="wet">wet</option>
            <option value="dry">dry</option>
            <option value="cure">cure</option>
          </select>
        </label>
        <label>
          weight (g)
          <input type="number" min="0.01" step="0.01" value={weightG} onChange={(e) => setWeightG(e.target.value)} />
        </label>
        <label>
          room
          <RoomSelect rooms={rooms} value={roomId} onChange={setRoomId} />
        </label>
        <button disabled={submitting || !currentOperator || !harvestId || !weightG || !roomId} onClick={submit}>
          {submitting ? "logging…" : "log weight"}
        </button>
        {success && <span className="form-success" role="status">✓ weight logged</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

function WeighHistory({ harvests, rooms, refreshKey }: { harvests: Harvest[]; rooms: Room[]; refreshKey: number }) {
  const [harvestId, setHarvestId] = useState("");
  const [logs, setLogs] = useState<HarvestWeightLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!harvestId) {
      setLogs(null);
      return;
    }
    complianceApi
      .getHarvestWeightLogs(harvestId)
      .then(setLogs)
      .catch((err) => setError(errorMessage(err)));
  }, [harvestId, refreshKey]);

  return (
    <div className="action-subsection">
      <p className="card-subtitle">View weigh-in history</p>
      <div className="quick-form" style={{ flexDirection: "column", alignItems: "stretch" }}>
        <label>
          harvest
          <select value={harvestId} onChange={(e) => setHarvestId(e.target.value)}>
            <option value="">{harvests.length === 0 ? "no harvests yet" : "select a harvest…"}</option>
            {harvests.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name} — {h.strain}
              </option>
            ))}
          </select>
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        {harvestId &&
          (logs === null ? (
            <p className="stat-label">Loading…</p>
          ) : logs.length === 0 ? (
            <p className="stat-label">no weigh-ins logged for this harvest yet</p>
          ) : (
            <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>stage</th>
                  <th>weight</th>
                  <th>room</th>
                  <th>recorded</th>
                  <th>by</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.stage}</td>
                    <td>{log.weight_g}g</td>
                    <td>{roomLabel(rooms, log.room_id)}</td>
                    <td>{formatDateTime(log.recorded_at)}</td>
                    <td>{log.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          ))}
      </div>
    </div>
  );
}

function FinishHarvestForm({
  harvests,
  currentOperator,
  onDone,
}: {
  harvests: Harvest[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const openHarvests = harvests.filter((h) => h.status !== "finished");
  const [harvestId, setHarvestId] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.finishHarvest(harvestId, currentOperator.id);
      setHarvestId("");
      onDone();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">Mark a harvest finished</p>
      <div className="quick-form">
        <label>
          harvest
          <select value={harvestId} onChange={(e) => setHarvestId(e.target.value)}>
            <option value="">{openHarvests.length === 0 ? "nothing to finish" : "select a harvest…"}</option>
            {openHarvests.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name} — {h.strain}
              </option>
            ))}
          </select>
        </label>
        <button disabled={submitting || !currentOperator || !harvestId} onClick={submit}>
          {submitting ? "finishing…" : "mark finished"}
        </button>
        {success && <span className="form-success" role="status">✓ marked finished</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

function PackageHarvestForm({
  harvests,
  rooms,
  currentOperator,
  onDone,
}: {
  harvests: Harvest[];
  rooms: Room[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const [harvestId, setHarvestId] = useState("");
  const [itemName, setItemName] = useState("");
  const [weightG, setWeightG] = useState("");
  const [roomId, setRoomId] = useState("");
  const [tag, setTag] = useState("");
  const [isProductionBatch, setIsProductionBatch] = useState(false);
  const [isDonation, setIsDonation] = useState(false);
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.packageHarvest(harvestId, {
        item_name: itemName,
        weight_g: Number(weightG),
        room_id: roomId,
        tag: tag || undefined,
        is_production_batch: isProductionBatch,
        is_donation: isDonation,
        operator_id: currentOperator.id,
      });
      setItemName("");
      setWeightG("");
      setTag("");
      setIsProductionBatch(false);
      setIsDonation(false);
      onDone();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">Create a package from a harvest</p>
      <div className="quick-form">
        <label>
          from harvest
          <select value={harvestId} onChange={(e) => setHarvestId(e.target.value)}>
            <option value="">{harvests.length === 0 ? "no harvests yet" : "select a harvest…"}</option>
            {harvests.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name} — {h.strain}
              </option>
            ))}
          </select>
        </label>
        <label>
          item name
          <input value={itemName} onChange={(e) => setItemName(e.target.value)} placeholder="e.g. GMO — 3.5g flower" />
        </label>
        <label>
          weight (g)
          <input type="number" min="0.01" step="0.01" value={weightG} onChange={(e) => setWeightG(e.target.value)} />
        </label>
        <label>
          room
          <RoomSelect rooms={rooms} value={roomId} onChange={setRoomId} />
        </label>
        <label>
          tag (optional)
          <input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="auto-generated if blank" />
        </label>
        <label>
          <span className="checkbox-label">
            <input type="checkbox" checked={isProductionBatch} onChange={(e) => setIsProductionBatch(e.target.checked)} />
            production batch
          </span>
          <span className="field-hint">
            This package was made through a manufacturing/processing run (e.g. pre-rolls, extract, infused product)
            rather than packaged straight from harvested flower — check this so it's traceable back to that run.
          </span>
        </label>
        <label>
          <span className="checkbox-label">
            <input type="checkbox" checked={isDonation} onChange={(e) => setIsDonation(e.target.checked)} />
            donation
          </span>
          <span className="field-hint">Given away rather than sold — check this for compassionate-care or sample product.</span>
        </label>
        <button disabled={submitting || !currentOperator || !harvestId || !itemName || !weightG || !roomId} onClick={submit}>
          {submitting ? "creating…" : "create package"}
        </button>
        {success && <span className="form-success" role="status">✓ package created</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function PlantsHarvests() {
  const rooms = useRooms();
  const {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();

  const [harvests, setHarvests] = useState<Harvest[] | null>(null);
  const [strains, setStrains] = useState<Strain[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = () => {
    complianceApi.getHarvests().then(setHarvests).catch((err) => setError(errorMessage(err)));
    strainsApi.getStrains().then(setStrains).catch(() => setStrains([]));
    setRefreshKey((k) => k + 1);
  };

  useEffect(refresh, []);

  if (error) return <div className="page-status">Failed to load harvest data: {error}</div>;

  return (
    <div className="page">
      <TopNav />

      <div className="section-label">Plants &amp; harvest</div>
      <PlantsSubNav />
      <Card>
        <p className="card-subtitle">
          A harvest gathers wet material from one or more plants, gets weighed at each stage (wet → dry → cure), and
          finishes as one or more packages.
        </p>
        <OperatorPicker
          operators={operators}
          currentOperatorId={currentOperatorId}
          onChange={changeCurrentOperator}
          onOperatorCreated={handleOperatorCreated}
          onOperatorUpdated={handleOperatorUpdated}
          onOperatorDeactivated={handleOperatorDeactivated}
        />
      </Card>

      <div className="section-label">Harvests</div>
      <Card>
        {harvests ? <HarvestsTable harvests={harvests} rooms={rooms} /> : <p className="stat-label">Loading…</p>}
        <CreateHarvestForm rooms={rooms} strains={strains} currentOperator={currentOperator} onCreated={refresh} />
        <WeighHarvestForm harvests={harvests ?? []} rooms={rooms} currentOperator={currentOperator} onDone={refresh} />
        <WeighHistory harvests={harvests ?? []} rooms={rooms} refreshKey={refreshKey} />
        <FinishHarvestForm harvests={harvests ?? []} currentOperator={currentOperator} onDone={refresh} />
        <PackageHarvestForm harvests={harvests ?? []} rooms={rooms} currentOperator={currentOperator} onDone={refresh} />
      </Card>
    </div>
  );
}
