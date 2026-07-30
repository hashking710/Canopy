import { useEffect, useState } from "react";
import { complianceApi } from "../api/complianceClient";
import type { Harvest, LabTest, Operator, Package, StateComplianceRules } from "../api/complianceTypes";
import { Badge } from "./Badge";
import { useSubmitState } from "../hooks/useSubmitState";
import { formatDate } from "../lib/formatDateTime";
import { roomLabel } from "../lib/roomLabel";
import type { Room } from "../types";

// Process methods that involve a chemical solvent — used to flag packages that
// likely need residual-solvent testing before sale in states that require it.
// Rosin/press/decarb are mechanical/thermal, not solvent-based.
const SOLVENT_METHODS = ["BHO Extraction", "CO2 Extraction", "Ethanol Extraction"];

function isSolventDerived(pkg: Package): boolean {
  return pkg.process_method !== null && SOLVENT_METHODS.includes(pkg.process_method);
}

// The most recent residual-solvent test result for a package, or null if it's never
// been tested at all — "failed" and "never tested" are very different situations (a
// failed batch likely needs to be destroyed, not just retested) and must not collapse
// into the same generic warning.
function latestSolventTestResult(pkg: Package, tests: LabTest[]): LabTest["result"] | null {
  const relevant = tests.filter((t) => t.package_id === pkg.id && t.test_type === "residual_solvents");
  if (relevant.length === 0) return null;
  // tested_at is a plain date — ties (two tests logged the same day) break on
  // recorded_at, the real timestamp of when each result was entered into the system.
  return [...relevant].sort(
    (a, b) => b.tested_at.localeCompare(a.tested_at) || b.recorded_at.localeCompare(a.recorded_at),
  )[0].result;
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function packageLabel(pkg: Package): string {
  return `${pkg.item_name} — ${pkg.id} (${pkg.status})`;
}

function PackagesTable({
  packages,
  rooms,
  harvests,
  labTests,
  testingRequired,
}: {
  packages: Package[];
  rooms: Room[];
  harvests: Harvest[];
  labTests: LabTest[];
  testingRequired: boolean;
}) {
  if (packages.length === 0) return <p className="stat-label">no packages yet</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>tag</th>
          <th>item</th>
          <th>source</th>
          <th>weight</th>
          <th>room</th>
          <th>created</th>
          <th>status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {packages.map((p) => (
          <tr key={p.id}>
            <td>{p.id}</td>
            <td>{p.item_name}</td>
            <td>
              {p.source_package_id ? (
                <>
                  {p.process_method} <span className="stat-label">of {p.source_package_id}</span>
                  {p.process_yield_pct !== null && <span className="stat-label"> · {p.process_yield_pct.toFixed(1)}% yield</span>}
                </>
              ) : (
                (harvests.find((h) => h.id === p.harvest_id)?.name ?? p.harvest_id ?? "—")
              )}
            </td>
            <td>{p.weight_g}g</td>
            <td>{roomLabel(rooms, p.room_id)}</td>
            <td>{formatDate(p.created_at)}</td>
            <td>
              <Badge text={p.status} variant={p.status === "active" ? "ok" : "default"} />
            </td>
            <td>
              {testingRequired &&
                p.status === "active" &&
                isSolventDerived(p) &&
                (() => {
                  const result = latestSolventTestResult(p, labTests);
                  if (result === "pass") return null;
                  if (result === "fail") return <Badge text="FAILED solvent test" variant="danger" />;
                  return <Badge text="needs solvent testing" variant="warn" />;
                })()}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

const PACKAGE_STATUSES = ["active", "sold", "destroyed", "transferred", "processed"] as const;

function PackageStatusForm({
  packages,
  currentOperator,
  onDone,
}: {
  packages: Package[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const [packageId, setPackageId] = useState("");
  const [status, setStatus] = useState<(typeof PACKAGE_STATUSES)[number]>("sold");
  const { submitting, error, success, run } = useSubmitState();

  const selectedPackage = packages.find((p) => p.id === packageId) ?? null;

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      if (
        status !== "active" &&
        !confirm(
          `Mark ${selectedPackage ? packageLabel(selectedPackage) : "this package"} as "${status}"? This is final — it can't be changed back once set.`,
        )
      )
        return;
      await complianceApi.updatePackageStatus(packageId, status, currentOperator.id);
      setPackageId("");
      onDone();
    });

  return (
    <div className="quick-form">
      <label>
        package
        <select value={packageId} onChange={(e) => setPackageId(e.target.value)}>
          <option value="">{packages.length === 0 ? "no packages yet" : "select a package…"}</option>
          {packages.map((p) => (
            <option key={p.id} value={p.id}>
              {packageLabel(p)}
            </option>
          ))}
        </select>
      </label>
      <label>
        new status
        <select value={status} onChange={(e) => setStatus(e.target.value as (typeof PACKAGE_STATUSES)[number])}>
          {PACKAGE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span className="field-hint">
          Every status except "active" is final and can't be changed back — the package physically left the
          facility, was destroyed, or was consumed into another package.
        </span>
      </label>
      <button disabled={submitting || !currentOperator || !packageId} onClick={submit}>
        {submitting ? "updating…" : "update status"}
      </button>
      {success && <span className="form-success" role="status">✓ status updated</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

// Real extraction/refinement chains: trim/flower -> BHO/CO2/ethanol extraction ->
// crude oil -> winterization (strips fats/waxes) -> short-path distillation ->
// distillate. Each step processes an existing package into a new one, so a package
// can itself be the source for the *next* processing step (crude -> distillate),
// not just harvest -> package once.
const PROCESS_METHODS = [
  "BHO Extraction",
  "CO2 Extraction",
  "Ethanol Extraction",
  "Winterization",
  "Short-Path Distillation",
  "Decarboxylation",
  "Rosin Press",
  "Other",
] as const;

function ProcessPackageForm({
  packages,
  rooms,
  currentOperator,
  onDone,
}: {
  packages: Package[];
  rooms: Room[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const [sourceId, setSourceId] = useState("");
  const [itemName, setItemName] = useState("");
  const [weightG, setWeightG] = useState("");
  const [roomId, setRoomId] = useState("");
  const [method, setMethod] = useState<(typeof PROCESS_METHODS)[number]>("BHO Extraction");
  const [customMethod, setCustomMethod] = useState("");
  const [tag, setTag] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const source = packages.find((p) => p.id === sourceId) ?? null;
  const effectiveMethod = method === "Other" ? customMethod : method;
  const previewYield = source && weightG ? ((Number(weightG) / source.weight_g) * 100).toFixed(1) : null;

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.processPackage(sourceId, {
        item_name: itemName,
        weight_g: Number(weightG),
        room_id: roomId,
        process_method: effectiveMethod,
        tag: tag || undefined,
        operator_id: currentOperator.id,
      });
      setItemName("");
      setWeightG("");
      setTag("");
      onDone();
    });

  return (
    <div className="quick-form">
      <label>
        source package
        <select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
          <option value="">{packages.length === 0 ? "no packages yet" : "select a package…"}</option>
          {packages.map((p) => (
            <option key={p.id} value={p.id}>
              {packageLabel(p)}
            </option>
          ))}
        </select>
      </label>
      <label>
        method
        <select value={method} onChange={(e) => setMethod(e.target.value as (typeof PROCESS_METHODS)[number])}>
          {PROCESS_METHODS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>
      {method === "Other" && (
        <label>
          method (custom)
          <input value={customMethod} onChange={(e) => setCustomMethod(e.target.value)} placeholder="e.g. Live Rosin Press" />
        </label>
      )}
      <label>
        output item name
        <input value={itemName} onChange={(e) => setItemName(e.target.value)} placeholder="e.g. GMO Distillate" />
      </label>
      <label>
        output weight (g)
        <input value={weightG} onChange={(e) => setWeightG(e.target.value)} type="number" min="0.01" step="0.01" />
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
        tag (optional)
        <input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="auto-generated if blank" />
      </label>
      <button
        disabled={submitting || !currentOperator || !sourceId || !itemName || !weightG || !roomId || !effectiveMethod}
        onClick={submit}
      >
        {submitting ? "processing…" : "process package"}
      </button>
      {previewYield && <span className="stat-label">yield: {previewYield}% of source weight</span>}
      {success && <span className="form-success" role="status">✓ package processed</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

function LineageViewer({ packages }: { packages: Package[] }) {
  const [packageId, setPackageId] = useState("");
  const [chain, setChain] = useState<Package[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!packageId) {
      setChain(null);
      return;
    }
    complianceApi
      .getPackageLineage(packageId)
      .then(setChain)
      .catch((err) => setError(errorMessage(err)));
  }, [packageId]);

  return (
    <div className="action-subsection">
      <p className="card-subtitle">View a package's lineage</p>
      <div className="quick-form" style={{ flexDirection: "column", alignItems: "stretch" }}>
        <label>
          package
          <select value={packageId} onChange={(e) => setPackageId(e.target.value)}>
            <option value="">{packages.length === 0 ? "no packages yet" : "select a package…"}</option>
            {packages.map((p) => (
              <option key={p.id} value={p.id}>
                {packageLabel(p)}
              </option>
            ))}
          </select>
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        {chain && (
          <div className="lineage-chain">
            {chain.map((pkg, i) => (
              <div className="lineage-step" key={pkg.id}>
                {i > 0 && <span className="lineage-arrow">→ {pkg.process_method}</span>}
                <span className="lineage-item">
                  {pkg.item_name} <span className="stat-label">({pkg.weight_g}g, {pkg.id})</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const LAB_TEST_TYPES = ["residual_solvents", "potency", "microbial", "pesticides", "heavy_metals", "other"] as const;

function RecordLabTestForm({
  packages,
  currentOperator,
  onDone,
}: {
  packages: Package[];
  currentOperator: Operator | null;
  onDone: () => void;
}) {
  const [packageId, setPackageId] = useState("");
  const [labName, setLabName] = useState("");
  const [testType, setTestType] = useState<(typeof LAB_TEST_TYPES)[number]>("residual_solvents");
  const [result, setResult] = useState<"pass" | "fail" | "pending">("pending");
  const [thcPct, setThcPct] = useState("");
  const [cbdPct, setCbdPct] = useState("");
  const [testedAt, setTestedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const { submitting, error, success, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      if (!currentOperator) return;
      await complianceApi.createLabTest(packageId, {
        lab_name: labName,
        test_type: testType,
        result,
        thc_pct: thcPct ? Number(thcPct) : undefined,
        cbd_pct: cbdPct ? Number(cbdPct) : undefined,
        notes: notes || undefined,
        tested_at: testedAt,
        operator_id: currentOperator.id,
      });
      setLabName("");
      setThcPct("");
      setCbdPct("");
      setNotes("");
      onDone();
    });

  return (
    <div className="quick-form">
      <label>
        package
        <select value={packageId} onChange={(e) => setPackageId(e.target.value)}>
          <option value="">{packages.length === 0 ? "no packages yet" : "select a package…"}</option>
          {packages.map((p) => (
            <option key={p.id} value={p.id}>
              {packageLabel(p)}
            </option>
          ))}
        </select>
      </label>
      <label>
        lab
        <input value={labName} onChange={(e) => setLabName(e.target.value)} placeholder="lab name" />
      </label>
      <label>
        test type
        <select value={testType} onChange={(e) => setTestType(e.target.value as (typeof LAB_TEST_TYPES)[number])}>
          {LAB_TEST_TYPES.map((t) => (
            <option key={t} value={t}>
              {t.replace("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <label>
        result
        <select value={result} onChange={(e) => setResult(e.target.value as "pass" | "fail" | "pending")}>
          <option value="pending">pending</option>
          <option value="pass">pass</option>
          <option value="fail">fail</option>
        </select>
      </label>
      <label>
        THC % (optional)
        <input value={thcPct} onChange={(e) => setThcPct(e.target.value)} type="number" />
      </label>
      <label>
        CBD % (optional)
        <input value={cbdPct} onChange={(e) => setCbdPct(e.target.value)} type="number" />
      </label>
      <label>
        tested on
        <input value={testedAt} onChange={(e) => setTestedAt(e.target.value)} type="date" />
      </label>
      <label>
        notes (optional)
        <input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <button disabled={submitting || !currentOperator || !packageId || !labName} onClick={submit}>
        {submitting ? "recording…" : "record test"}
      </button>
      {success && <span className="form-success" role="status">✓ test recorded</span>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

// COA files are photographed/scanned lab reports as often as clean PDFs — accept
// the same types the backend does (services/coa_storage.py's _ALLOWED_CONTENT_TYPES).
const COA_ACCEPT = "application/pdf,image/png,image/jpeg";

function CoaCell({
  test,
  currentOperator,
  onUploaded,
}: {
  test: LabTest;
  currentOperator: Operator | null;
  onUploaded: () => void;
}) {
  const { submitting, error, run } = useSubmitState();

  const handleFile = (file: File | undefined) => {
    if (!file || !currentOperator) return;
    run(async () => {
      await complianceApi.uploadLabTestCoa(test.id, currentOperator.id, file);
      onUploaded();
    });
  };

  if (test.coa_filename) {
    return (
      <button
        type="button"
        className="inline-button"
        onClick={() => complianceApi.downloadLabTestCoa(test.id, test.coa_filename!)}
        title={test.coa_filename}
      >
        view COA
      </button>
    );
  }

  return (
    <label className="inline-button" style={{ cursor: currentOperator ? "pointer" : "not-allowed" }}>
      {submitting ? "uploading…" : "attach COA"}
      <input
        type="file"
        accept={COA_ACCEPT}
        style={{ display: "none" }}
        disabled={submitting || !currentOperator}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {error && <span className="form-error" role="alert">{error}</span>}
    </label>
  );
}

function LabTestsTable({
  tests,
  packages,
  currentOperator,
  onCoaUploaded,
}: {
  tests: LabTest[];
  packages: Package[];
  currentOperator: Operator | null;
  onCoaUploaded: () => void;
}) {
  if (tests.length === 0) return <p className="stat-label">no lab tests recorded yet</p>;
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>package</th>
          <th>lab</th>
          <th>type</th>
          <th>THC</th>
          <th>CBD</th>
          <th>tested</th>
          <th>result</th>
          <th>COA</th>
        </tr>
      </thead>
      <tbody>
        {tests.map((t) => (
          <tr key={t.id}>
            <td>{packages.find((p) => p.id === t.package_id)?.item_name ?? t.package_id}</td>
            <td>{t.lab_name}</td>
            <td>{t.test_type.replace("_", " ")}</td>
            <td>{t.thc_pct !== null ? `${t.thc_pct}%` : "—"}</td>
            <td>{t.cbd_pct !== null ? `${t.cbd_pct}%` : "—"}</td>
            <td>{t.tested_at}</td>
            <td>
              <Badge
                text={t.result}
                variant={t.result === "pass" ? "ok" : t.result === "fail" ? "danger" : "warn"}
              />
            </td>
            <td>
              <CoaCell test={t} currentOperator={currentOperator} onUploaded={onCoaUploaded} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

export function PackagesSection({
  packages,
  rooms,
  harvests,
  currentOperator,
  stateRules,
  onDone,
}: {
  packages: Package[];
  rooms: Room[];
  harvests: Harvest[];
  currentOperator: Operator | null;
  stateRules: StateComplianceRules | null;
  onDone: () => void;
}) {
  const [labTests, setLabTests] = useState<LabTest[] | null>(null);
  const [labTestsError, setLabTestsError] = useState<string | null>(null);

  const refreshLabTests = () => {
    complianceApi.getAllLabTests().then(setLabTests).catch((err) => setLabTestsError(errorMessage(err)));
  };

  useEffect(refreshLabTests, [packages]);

  const handleDone = () => {
    onDone();
    refreshLabTests();
  };

  const testingRequired = stateRules?.testing_required_for_solvent_extracts === true;

  return (
    <>
      <div className="section-label">Packages</div>
      <div className="card">
        <div className="card-body">
          <PackagesTable packages={packages} rooms={rooms} harvests={harvests} labTests={labTests ?? []} testingRequired={testingRequired} />
          <PackageStatusForm packages={packages} currentOperator={currentOperator} onDone={handleDone} />
        </div>
      </div>

      <div className="section-label">Process a package (extraction, winterization, distillation, …)</div>
      <div className="card">
        <div className="card-body">
          <p className="card-subtitle">
            Turn a package into a new one — flower/trim into BHO crude, crude into winterized oil, winterized oil
            into distillate. The source package is left alone; mark it "processed" above once it's fully consumed.
          </p>
          <ProcessPackageForm packages={packages} rooms={rooms} currentOperator={currentOperator} onDone={handleDone} />
          <LineageViewer packages={packages} />
        </div>
      </div>

      <div className="section-label">Lab tests</div>
      <div className="card">
        <div className="card-body">
          {stateRules && (
            <p className="card-subtitle">
              {stateRules.testing_required_for_solvent_extracts === true
                ? `${stateRules.state_name} requires residual-solvent testing on BHO/CO2/ethanol-derived packages before sale.`
                : stateRules.testing_required_for_solvent_extracts === false
                  ? `${stateRules.state_name}'s regulations, as researched, do not require this.`
                  : `Whether ${stateRules.state_name} requires solvent testing hasn't been verified yet.`}
              {stateRules.testing_note && ` ${stateRules.testing_note}`}
            </p>
          )}
          {labTestsError && <p className="form-error" role="alert">{labTestsError}</p>}
          {labTests ? (
            <LabTestsTable tests={labTests} packages={packages} currentOperator={currentOperator} onCoaUploaded={refreshLabTests} />
          ) : (
            <p className="stat-label">Loading…</p>
          )}
          <RecordLabTestForm packages={packages} currentOperator={currentOperator} onDone={handleDone} />
        </div>
      </div>
    </>
  );
}
