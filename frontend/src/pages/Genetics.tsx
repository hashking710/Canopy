import { useEffect, useState } from "react";
import { strainsApi } from "../api/strainsClient";
import type { Strain, StrainType } from "../api/strainsTypes";
import type { Operator } from "../api/complianceTypes";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { OperatorPicker } from "../components/OperatorPicker";
import { PlantsSubNav } from "../components/PlantsSubNav";
import { TopNav } from "../components/TopNav";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import { useRowAction } from "../hooks/useRowAction";
import { useSubmitState } from "../hooks/useSubmitState";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

const STRAIN_TYPES: StrainType[] = ["indica", "sativa", "hybrid", "unknown"];

function strainTypeBadgeVariant(type: StrainType): "ok" | "warn" | "default" {
  if (type === "indica") return "warn";
  if (type === "sativa") return "ok";
  return "default";
}

function potencyText(strain: Strain): string {
  const parts: string[] = [];
  if (strain.thc_pct_typical != null) parts.push(`${strain.thc_pct_typical}% THC`);
  if (strain.cbd_pct_typical != null) parts.push(`${strain.cbd_pct_typical}% CBD`);
  return parts.length > 0 ? parts.join(" / ") : "—";
}

function StrainsTable({
  strains,
  onDeactivate,
  pendingId,
}: {
  strains: Strain[];
  onDeactivate: (id: string) => void;
  pendingId: string | null;
}) {
  if (strains.length === 0) return <p className="stat-label">no strains registered yet</p>;
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>name</th>
            <th>type</th>
            <th>lineage</th>
            <th>typical potency</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {strains.map((strain) => (
            <tr key={strain.id}>
              <td>{strain.name}</td>
              <td>
                <Badge text={strain.strain_type} variant={strainTypeBadgeVariant(strain.strain_type)} />
              </td>
              <td>{strain.lineage || "—"}</td>
              <td>{potencyText(strain)}</td>
              <td>
                <button
                  className="inline-button"
                  onClick={() => onDeactivate(strain.id)}
                  disabled={pendingId === strain.id}
                >
                  {pendingId === strain.id ? "removing…" : "deactivate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CreateStrainForm({
  currentOperator,
  onCreated,
}: {
  currentOperator: Operator | null;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [lineage, setLineage] = useState("");
  const [strainType, setStrainType] = useState<StrainType>("hybrid");
  const [description, setDescription] = useState("");
  const [thc, setThc] = useState("");
  const [cbd, setCbd] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      // Strains are role-gated (role >= "operator", see routers/strains.py) — an
      // explicit error here beats a silent no-op if nobody's picked who they are
      // (below) yet.
      if (!currentOperator) throw new Error("pick who you are (below) before adding a strain");
      await strainsApi.createStrain({
        name,
        lineage,
        strain_type: strainType,
        description,
        thc_pct_typical: thc ? Number(thc) : null,
        cbd_pct_typical: cbd ? Number(cbd) : null,
        operator_id: currentOperator.id,
      });
      setName("");
      setLineage("");
      setDescription("");
      setThc("");
      setCbd("");
      onCreated();
    });

  return (
    <div>
      <div className="quick-form">
        <label>
          name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. GMO" />
        </label>
        <label>
          lineage
          <input
            value={lineage}
            onChange={(e) => setLineage(e.target.value)}
            placeholder="e.g. Chemdog x Girl Scout Cookies"
          />
        </label>
        <label>
          type
          <select value={strainType} onChange={(e) => setStrainType(e.target.value as StrainType)}>
            {STRAIN_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          typical THC %
          <input value={thc} onChange={(e) => setThc(e.target.value)} type="number" step="0.1" />
        </label>
        <label>
          typical CBD %
          <input value={cbd} onChange={(e) => setCbd(e.target.value)} type="number" step="0.1" />
        </label>
        <button disabled={submitting || !name} onClick={submit}>
          {submitting ? "adding…" : "add strain"}
        </button>
      </div>
      <label className="field-block">
        description
        <input value={description} onChange={(e) => setDescription(e.target.value)} style={{ width: "100%" }} />
      </label>
      {success && <span className="form-success" role="status">✓ strain added</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

export function Genetics() {
  const [strains, setStrains] = useState<Strain[] | null>(null);
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
  const deactivateAction = useRowAction<string>();

  const refresh = () => {
    strainsApi.getStrains().then(setStrains).catch((err) => setError(errorMessage(err)));
  };

  useEffect(refresh, []);

  const deactivate = (id: string) =>
    deactivateAction.run(id, async () => {
      if (!currentOperator) throw new Error("pick who you are (below) before deactivating a strain");
      await strainsApi.deactivateStrain(id, currentOperator.id);
      refresh();
    });

  if (error) return <div className="page-status">Failed to load genetics: {error}</div>;

  return (
    <div className="page">
      <TopNav />

      <div className="section-label">Plants &amp; harvest</div>
      <PlantsSubNav />
      <Card>
        <p className="card-subtitle">Strain registry</p>
        <p className="card-footnote" style={{ marginTop: 12, paddingTop: 0, borderTop: "none" }}>
          Optional structured genetics — lineage, type, and typical potency — that
          plant batches, plants, and harvests can link to. Feeds menu sync (see
          Settings) with real genetics and THC/CBD data instead of just a free-text
          strain name.
        </p>
      </Card>

      <div className="section-label">Registered strains</div>
      <Card>
        <OperatorPicker
          operators={operators}
          currentOperatorId={currentOperatorId}
          onChange={changeCurrentOperator}
          onOperatorCreated={handleOperatorCreated}
          onOperatorUpdated={handleOperatorUpdated}
          onOperatorDeactivated={handleOperatorDeactivated}
        />
        {strains ? (
          <StrainsTable strains={strains} onDeactivate={deactivate} pendingId={deactivateAction.pendingId} />
        ) : (
          <p className="stat-label">Loading…</p>
        )}
        {deactivateAction.error && <p className="form-error" role="alert">{deactivateAction.error}</p>}
        <CreateStrainForm currentOperator={currentOperator} onCreated={refresh} />
      </Card>
    </div>
  );
}
