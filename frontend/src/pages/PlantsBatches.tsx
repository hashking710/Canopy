import { useEffect, useState } from "react";
import { complianceApi } from "../api/complianceClient";
import type { Harvest, Operator, Plant, PlantBatch } from "../api/complianceTypes";
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
import { roomLabel } from "../lib/roomLabel";
import type { Room } from "../types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// ---------------------------------------------------------------------------
// Plant batches
// ---------------------------------------------------------------------------

function BatchesTable({ batches, rooms }: { batches: PlantBatch[]; rooms: Room[] }) {
  if (batches.length === 0) return <p className="stat-label">no plant batches yet</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>name</th>
          <th>strain</th>
          <th>type</th>
          <th>room</th>
          <th>planted</th>
          <th>untracked</th>
          <th>tracked</th>
          <th>harvested</th>
          <th>destroyed</th>
          <th>status</th>
        </tr>
      </thead>
      <tbody>
        {batches.map((b) => (
          <tr key={b.id}>
            <td>{b.name}</td>
            <td>{b.strain}</td>
            <td>{b.batch_type}</td>
            <td>{roomLabel(rooms, b.room_id)}</td>
            <td>{b.planted_date}</td>
            <td>{b.untracked_count}</td>
            <td>{b.tracked_count}</td>
            <td>{b.harvested_count}</td>
            <td>{b.destroyed_count}</td>
            <td>
              <Badge text={b.status} variant={b.status === "active" ? "ok" : "default"} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function CreateBatchForm({
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
  const [batchType, setBatchType] = useState<"Seed" | "Clone">("Clone");
  const [strain, setStrain] = useState("");
  const [strainId, setStrainId] = useState("");
  const [roomId, setRoomId] = useState("");
  const [plantedDate, setPlantedDate] = useState(todayIso());
  const [count, setCount] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  // Picking a registry strain auto-fills the free-text field, which stays what's
  // actually required/authoritative (METRC's own model has no registry concept) —
  // strain_id is purely an additional, optional link for genetics/potency roll-up
  // and menu sync (see docs/architecture.md).
  const pickRegistryStrain = (id: string) => {
    setStrainId(id);
    const picked = strains.find((s) => s.id === id);
    if (picked) setStrain(picked.name);
  };

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.createPlantBatch({
        name,
        batch_type: batchType,
        strain,
        strain_id: strainId || null,
        room_id: roomId,
        planted_date: plantedDate,
        count: Number(count),
        operator_id: currentOperator.id,
      });
      setName("");
      setStrain("");
      setStrainId("");
      setRoomId("");
      setCount("");
      onCreated();
    });

  return (
    <div className="quick-form">
      <label>
        batch name
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. GHA-2026-014" />
      </label>
      <label>
        type
        <select value={batchType} onChange={(e) => setBatchType(e.target.value as "Seed" | "Clone")}>
          <option value="Clone">Clone</option>
          <option value="Seed">Seed</option>
        </select>
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
          placeholder="e.g. GMO"
        />
      </label>
      <label>
        room
        <RoomSelect rooms={rooms} value={roomId} onChange={setRoomId} />
      </label>
      <label>
        planted date
        <input type="date" value={plantedDate} onChange={(e) => setPlantedDate(e.target.value)} />
      </label>
      <label>
        count
        <input type="number" min="1" value={count} onChange={(e) => setCount(e.target.value)} />
      </label>
      <button disabled={submitting || !currentOperator || !name || !strain || !roomId || !count} onClick={submit}>
        {submitting ? "creating…" : "create batch"}
      </button>
      {success && <span className="form-success" role="status">✓ batch created</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

function TagPlantsForm({
  batches,
  rooms,
  currentOperator,
  onTagged,
}: {
  batches: PlantBatch[];
  rooms: Room[];
  currentOperator: Operator | null;
  onTagged: () => void;
}) {
  const taggable = batches.filter((b) => b.untracked_count > 0);
  const [batchId, setBatchId] = useState("");
  const [count, setCount] = useState("");
  const [growthPhase, setGrowthPhase] = useState<"Vegetative" | "Flowering">("Vegetative");
  const [roomId, setRoomId] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const selectedBatch = taggable.find((b) => b.id === batchId) ?? null;

  const submit = () =>
    run(async () => {
      if (!currentOperator || !selectedBatch) return;
      await complianceApi.tagPlants(selectedBatch.id, {
        count: Number(count),
        growth_phase: growthPhase,
        room_id: roomId || undefined,
        operator_id: currentOperator.id,
      });
      setCount("");
      setRoomId("");
      onTagged();
    });

  return (
    <div className="quick-form">
      <label>
        batch
        <select value={batchId} onChange={(e) => setBatchId(e.target.value)}>
          <option value="">{taggable.length === 0 ? "no untracked plants available" : "select a batch…"}</option>
          {taggable.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} — {b.strain} ({b.untracked_count} untracked)
            </option>
          ))}
        </select>
      </label>
      <label>
        count to tag
        <input
          type="number"
          min="1"
          max={selectedBatch?.untracked_count}
          value={count}
          onChange={(e) => setCount(e.target.value)}
        />
      </label>
      <label>
        growth phase
        <select value={growthPhase} onChange={(e) => setGrowthPhase(e.target.value as "Vegetative" | "Flowering")}>
          <option value="Vegetative">Vegetative</option>
          <option value="Flowering">Flowering</option>
        </select>
      </label>
      <label>
        room (optional)
        <RoomSelect
          rooms={rooms}
          value={roomId}
          onChange={setRoomId}
          allowNone={`same as batch (${roomLabel(rooms, selectedBatch?.room_id ?? null)})`}
        />
      </label>
      <button disabled={submitting || !currentOperator || !selectedBatch || !count} onClick={submit}>
        {submitting ? "tagging…" : "tag plants"}
      </button>
      {success && <span className="form-success" role="status">✓ tagged</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individually tagged plants
// ---------------------------------------------------------------------------

function PlantsTable({
  plants,
  rooms,
  showAll,
  search,
}: {
  plants: Plant[];
  rooms: Room[];
  showAll: boolean;
  search: string;
}) {
  const statusFiltered = showAll ? plants : plants.filter((p) => p.status === "active");
  const query = search.trim().toLowerCase();
  const visible = query
    ? statusFiltered.filter(
        (p) =>
          p.id.toLowerCase().includes(query) ||
          p.strain.toLowerCase().includes(query) ||
          roomLabel(rooms, p.room_id).toLowerCase().includes(query),
      )
    : statusFiltered;

  if (statusFiltered.length === 0) {
    return <p className="stat-label">{showAll ? "no plants yet" : "no active plants"}</p>;
  }
  if (visible.length === 0) {
    return <p className="stat-label">no plants match "{search}"</p>;
  }
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>tag</th>
          <th>strain</th>
          <th>room</th>
          <th>phase</th>
          <th>tagged</th>
          <th>status</th>
        </tr>
      </thead>
      <tbody>
        {visible.map((p) => (
          <tr key={p.id}>
            <td>{p.id}</td>
            <td>{p.strain}</td>
            <td>{roomLabel(rooms, p.room_id)}</td>
            <td>{p.growth_phase}</td>
            <td>{p.tagged_date}</td>
            <td>
              <Badge text={p.status} variant={p.status === "active" ? "ok" : p.status === "destroyed" ? "danger" : "default"} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function plantOptionLabel(plant: Plant, rooms: Room[]): string {
  return `${plant.id} — ${plant.strain} (${roomLabel(rooms, plant.room_id)})`;
}

function MovePlantForm({
  activePlants,
  rooms,
  currentOperator,
  onDone,
}: {
  activePlants: Plant[];
  rooms: Room[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const [plantId, setPlantId] = useState("");
  const [roomId, setRoomId] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.movePlant(plantId, { room_id: roomId, operator_id: currentOperator.id });
      setPlantId("");
      setRoomId("");
      onDone();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">Move a plant to a different room</p>
      <div className="quick-form">
        <label>
          plant
          <select value={plantId} onChange={(e) => setPlantId(e.target.value)}>
            <option value="">{activePlants.length === 0 ? "no active plants" : "select a plant…"}</option>
            {activePlants.map((p) => (
              <option key={p.id} value={p.id}>
                {plantOptionLabel(p, rooms)}
              </option>
            ))}
          </select>
        </label>
        <label>
          move to room
          <RoomSelect rooms={rooms} value={roomId} onChange={setRoomId} />
        </label>
        <button disabled={submitting || !currentOperator || !plantId || !roomId} onClick={submit}>
          {submitting ? "moving…" : "move plant"}
        </button>
        {success && <span className="form-success" role="status">✓ moved</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

function HarvestPlantForm({
  activePlants,
  rooms,
  harvests,
  currentOperator,
  onDone,
}: {
  activePlants: Plant[];
  rooms: Room[];
  harvests: Harvest[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const openHarvests = harvests.filter((h) => h.status !== "finished");
  const [plantId, setPlantId] = useState("");
  const [harvestId, setHarvestId] = useState("");
  const [weightG, setWeightG] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.harvestPlant(plantId, {
        harvest_id: harvestId,
        weight_g: Number(weightG),
        operator_id: currentOperator.id,
      });
      setPlantId("");
      setWeightG("");
      onDone();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">Send a plant to harvest</p>
      <div className="quick-form">
        <label>
          plant
          <select value={plantId} onChange={(e) => setPlantId(e.target.value)}>
            <option value="">{activePlants.length === 0 ? "no active plants" : "select a plant…"}</option>
            {activePlants.map((p) => (
              <option key={p.id} value={p.id}>
                {plantOptionLabel(p, rooms)}
              </option>
            ))}
          </select>
        </label>
        <label>
          into harvest
          <select value={harvestId} onChange={(e) => setHarvestId(e.target.value)}>
            <option value="">{openHarvests.length === 0 ? "start a harvest first" : "select a harvest…"}</option>
            {openHarvests.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name} — {h.strain}
              </option>
            ))}
          </select>
        </label>
        <label>
          wet weight (g)
          <input type="number" min="0.01" step="0.01" value={weightG} onChange={(e) => setWeightG(e.target.value)} />
        </label>
        <button disabled={submitting || !currentOperator || !plantId || !harvestId || !weightG} onClick={submit}>
          {submitting ? "sending…" : "send to harvest"}
        </button>
        {success && <span className="form-success" role="status">✓ sent to harvest</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

const DESTROY_REASONS = ["Contamination", "Male Plants", "Pest", "Disease", "Testing", "Other"];
const DESTROY_METHODS = ["Compost", "Grinder", "Incineration", "Chemical Digestion"];

function DestroyPlantForm({
  activePlants,
  rooms,
  operators,
  currentOperator,
  onDone,
}: {
  activePlants: Plant[];
  rooms: Room[];
  operators: Operator[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const [plantId, setPlantId] = useState("");
  const [weightG, setWeightG] = useState("");
  const [method, setMethod] = useState("Compost");
  const [material, setMaterial] = useState("Soil");
  const [reason, setReason] = useState("Contamination");
  const [note, setNote] = useState("");
  const [pin, setPin] = useState("");
  const [witnessId, setWitnessId] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const witnessOptions = operators.filter((o) => o.id !== currentOperator?.id);

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      if (!confirm(`Destroy plant ${plantId} (${weightG}g, ${reason})? This can't be undone.`)) return;
      await complianceApi.destroyPlant(plantId, {
        weight_g: Number(weightG),
        method,
        material,
        reason,
        note: note || undefined,
        operator_id: currentOperator.id,
        pin: pin || undefined,
        witness_operator_id: witnessId || undefined,
      });
      setPlantId("");
      setWeightG("");
      setNote("");
      setPin("");
      setWitnessId("");
      onDone();
    });

  return (
    <div className="action-subsection">
      <p className="card-subtitle">Destroy a plant — irreversible, logged to the audit trail</p>
      <div className="quick-form">
        <label>
          plant
          <select value={plantId} onChange={(e) => setPlantId(e.target.value)}>
            <option value="">{activePlants.length === 0 ? "no active plants" : "select a plant…"}</option>
            {activePlants.map((p) => (
              <option key={p.id} value={p.id}>
                {plantOptionLabel(p, rooms)}
              </option>
            ))}
          </select>
        </label>
        <label>
          weight (g)
          <input type="number" min="0.01" step="0.01" value={weightG} onChange={(e) => setWeightG(e.target.value)} />
        </label>
        <label>
          method
          <select value={method} onChange={(e) => setMethod(e.target.value)}>
            {DESTROY_METHODS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          material
          <input value={material} onChange={(e) => setMaterial(e.target.value)} />
        </label>
        <label>
          reason
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            {DESTROY_REASONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        {currentOperator?.has_pin && (
          <label>
            your PIN
            <input value={pin} onChange={(e) => setPin(e.target.value)} type="password" placeholder="required" />
          </label>
        )}
        <label>
          witness (recommended)
          <select value={witnessId} onChange={(e) => setWitnessId(e.target.value)}>
            <option value="">none</option>
            {witnessOptions.map((op) => (
              <option key={op.id} value={op.id}>
                {op.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          note (optional)
          <input value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button className="danger" disabled={submitting || !currentOperator || !plantId || !weightG} onClick={submit}>
          {submitting ? "destroying…" : "destroy plant"}
        </button>
        {success && <span className="form-success" role="status">✓ destroyed</span>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function PlantsBatches() {
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

  const [batches, setBatches] = useState<PlantBatch[] | null>(null);
  const [plants, setPlants] = useState<Plant[] | null>(null);
  const [harvests, setHarvests] = useState<Harvest[] | null>(null);
  const [strains, setStrains] = useState<Strain[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showAllPlants, setShowAllPlants] = useState(false);
  const [plantSearch, setPlantSearch] = useState("");

  const refresh = () => {
    complianceApi.getPlantBatches().then(setBatches).catch((err) => setError(errorMessage(err)));
    complianceApi.getPlants().then(setPlants).catch((err) => setError(errorMessage(err)));
    complianceApi.getHarvests().then(setHarvests).catch((err) => setError(errorMessage(err)));
    strainsApi.getStrains().then(setStrains).catch(() => setStrains([]));
  };

  useEffect(refresh, []);

  if (error) return <div className="page-status">Failed to load plants &amp; harvest data: {error}</div>;

  const activePlants = (plants ?? []).filter((p) => p.status === "active");

  return (
    <div className="page">
      <TopNav />

      <div className="section-label">Plants &amp; harvest</div>
      <PlantsSubNav />
      <Card>
        <p className="card-subtitle">
          Plant batches become individually tagged plants as they're moved to canopy or begin flowering. Every
          action below is attributed to the signed-in operator and written to the audit trail on the compliance
          page.
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

      <div className="section-label">Plant batches</div>
      <Card>
        {batches ? <BatchesTable batches={batches} rooms={rooms} /> : <p className="stat-label">Loading…</p>}
        <CreateBatchForm rooms={rooms} strains={strains} currentOperator={currentOperator} onCreated={refresh} />
        <TagPlantsForm batches={batches ?? []} rooms={rooms} currentOperator={currentOperator} onTagged={refresh} />
      </Card>

      <div className="section-label-row">
        <div className="section-label">Individually tagged plants</div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <input
            value={plantSearch}
            onChange={(e) => setPlantSearch(e.target.value)}
            placeholder="search by tag, strain, or room…"
            className="plant-search-input"
          />
          <label className="stat-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={showAllPlants} onChange={(e) => setShowAllPlants(e.target.checked)} />
            show harvested/destroyed too
          </label>
        </div>
      </div>
      <Card>
        {plants ? (
          <PlantsTable plants={plants} rooms={rooms} showAll={showAllPlants} search={plantSearch} />
        ) : (
          <p className="stat-label">Loading…</p>
        )}
        <MovePlantForm activePlants={activePlants} rooms={rooms} currentOperator={currentOperator} onDone={refresh} />
        <HarvestPlantForm
          activePlants={activePlants}
          rooms={rooms}
          harvests={harvests ?? []}
          currentOperator={currentOperator}
          onDone={refresh}
        />
        <DestroyPlantForm
          activePlants={activePlants}
          rooms={rooms}
          operators={operators}
          currentOperator={currentOperator}
          onDone={refresh}
        />
      </Card>
    </div>
  );
}
