import { authHeaders } from "./authToken";
import { formatErrorDetail } from "./errors";
import type {
  AuditLogEntry,
  CreateHarvestBody,
  CreateLabTestBody,
  CreatePlantBatchBody,
  DestroyPlantBody,
  Harvest,
  HarvestPlantBody,
  HarvestWeightLog,
  LabTest,
  MovePlantBody,
  Operator,
  Package,
  PackageHarvestBody,
  PinPolicy,
  Plant,
  PlantBatch,
  ProcessPackageBody,
  ReconciliationRow,
  StateRulesResponse,
  TagPlantsBody,
  WasteEvent,
  WeighHarvestBody,
} from "./complianceTypes";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(formatErrorDetail(detail.detail, `${path} -> ${res.status}`));
  }
  return res.json() as Promise<T>;
}

async function downloadFile(path: string, filename: string): Promise<void> {
  // A plain <a href> download can't carry the Authorization header, so this fetches
  // as a blob (with auth) and triggers the save via a throwaway object URL instead.
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const complianceApi = {
  getWasteEvents: () => getJson<WasteEvent[]>("/api/compliance/waste-events"),
  markWasteReported: (id: number, operatorId: string) =>
    postJson(`/api/compliance/waste-events/${id}/mark-reported?operator_id=${encodeURIComponent(operatorId)}`, {}),
  getAuditLog: (limit = 50) => getJson<AuditLogEntry[]>(`/api/compliance/audit-log?limit=${limit}`),
  getReconciliation: () => getJson<ReconciliationRow[]>("/api/compliance/reconciliation"),
  recordPhysicalCount: (body: { room_id: string; counted_value: number; operator_id: string; note?: string }) =>
    postJson("/api/compliance/physical-counts", body),
  logWaste: (body: {
    source_type: string;
    source_id: string;
    room_id: string;
    waste_type: string;
    weight_g: number;
    method?: string;
    material?: string;
    reason?: string;
    note?: string;
    operator_id: string;
    pin?: string;
    witness_operator_id?: string;
  }) => postJson("/api/compliance/waste", body),
  verifyAuditLog: () => getJson<{ intact: boolean; broken_entry_ids: number[] }>("/api/compliance/audit-log/verify"),
  getStateRules: () => getJson<StateRulesResponse>("/api/compliance/state-rules"),
  setStateRules: (body: { state_code: string; operator_id: string }) =>
    postJson<StateRulesResponse>("/api/compliance/state-rules", body),
  getOperators: () => getJson<Operator[]>("/api/operators"),
  createOperator: (body: { name: string; pin?: string }) => postJson<Operator>("/api/operators", body),
  resetOperatorPin: (operatorId: string, pin: string | undefined) =>
    postJson<Operator>(`/api/operators/${operatorId}/reset-pin`, { pin }),
  deactivateOperator: (operatorId: string) =>
    postJson<{ id: string; name: string; active: boolean }>(`/api/operators/${operatorId}/deactivate`, {}),
  getPinPolicy: () => getJson<PinPolicy>("/api/operators/pin-policy"),
  setPinPolicy: (body: { require_operator_pins: boolean; operator_id: string }) =>
    postJson<PinPolicy>("/api/operators/pin-policy", body),
  exportAuditLogCsv: () => downloadFile("/api/compliance/export/audit-log", "canopy-audit-log.csv"),
  exportWasteEventsCsv: () => downloadFile("/api/compliance/export/waste-events", "canopy-waste-events.csv"),

  // Plant batches (immature lots)
  getPlantBatches: () => getJson<PlantBatch[]>("/api/compliance/plant-batches"),
  createPlantBatch: (body: CreatePlantBatchBody) => postJson<PlantBatch>("/api/compliance/plant-batches", body),
  tagPlants: (batchId: string, body: TagPlantsBody) =>
    postJson<{ batch: PlantBatch; plants: Plant[] }>(`/api/compliance/plant-batches/${batchId}/tag-plants`, body),

  // Individually tagged plants
  getPlants: () => getJson<Plant[]>("/api/compliance/plants"),
  movePlant: (plantId: string, body: MovePlantBody) => postJson<Plant>(`/api/compliance/plants/${plantId}/move`, body),
  destroyPlant: (plantId: string, body: DestroyPlantBody) =>
    postJson<{ plant: Plant; waste_event: WasteEvent }>(`/api/compliance/plants/${plantId}/destroy`, body),
  harvestPlant: (plantId: string, body: HarvestPlantBody) =>
    postJson<{ plant: Plant; harvest: Harvest }>(`/api/compliance/plants/${plantId}/harvest`, body),

  // Harvests
  getHarvests: () => getJson<Harvest[]>("/api/compliance/harvests"),
  createHarvest: (body: CreateHarvestBody) => postJson<Harvest>("/api/compliance/harvests", body),
  weighHarvest: (harvestId: string, body: WeighHarvestBody) =>
    postJson<HarvestWeightLog>(`/api/compliance/harvests/${harvestId}/weigh`, body),
  getHarvestWeightLogs: (harvestId: string) => getJson<HarvestWeightLog[]>(`/api/compliance/harvests/${harvestId}/weight-logs`),
  finishHarvest: (harvestId: string, operatorId: string) =>
    postJson<Harvest>(`/api/compliance/harvests/${harvestId}/finish`, { operator_id: operatorId }),
  packageHarvest: (harvestId: string, body: PackageHarvestBody) =>
    postJson<Package>(`/api/compliance/harvests/${harvestId}/package`, body),

  // Packages
  getPackages: () => getJson<Package[]>("/api/compliance/packages"),
  updatePackageStatus: (packageId: string, status: string, operatorId: string) =>
    postJson<Package>(`/api/compliance/packages/${packageId}/update-status`, { status, operator_id: operatorId }),
  processPackage: (packageId: string, body: ProcessPackageBody) =>
    postJson<Package>(`/api/compliance/packages/${packageId}/process`, body),
  getPackageLineage: (packageId: string) => getJson<Package[]>(`/api/compliance/packages/${packageId}/lineage`),

  // Lab tests
  createLabTest: (packageId: string, body: CreateLabTestBody) =>
    postJson<LabTest>(`/api/compliance/packages/${packageId}/lab-tests`, body),
  getPackageLabTests: (packageId: string) => getJson<LabTest[]>(`/api/compliance/packages/${packageId}/lab-tests`),
  getAllLabTests: (result?: string) => getJson<LabTest[]>(`/api/compliance/lab-tests${result ? `?result=${result}` : ""}`),
  uploadLabTestCoa: async (testId: string, operatorId: string, file: File): Promise<LabTest> => {
    const form = new FormData();
    form.append("operator_id", operatorId);
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/compliance/lab-tests/${testId}/coa`, {
      method: "POST",
      headers: authHeaders(), // no Content-Type — the browser sets the multipart boundary itself
      body: form,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(formatErrorDetail(detail.detail, `coa upload -> ${res.status}`));
    }
    return res.json() as Promise<LabTest>;
  },
  downloadLabTestCoa: (testId: string, filename: string) => downloadFile(`/api/compliance/lab-tests/${testId}/coa`, filename),
};
