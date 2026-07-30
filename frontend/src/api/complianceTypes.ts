export interface PlantBatch {
  id: string;
  name: string;
  batch_type: string;
  strain: string;
  room_id: string;
  planted_date: string;
  untracked_count: number;
  tracked_count: number;
  packaged_count: number;
  harvested_count: number;
  destroyed_count: number;
  status: string;
}

export interface Plant {
  id: string;
  batch_id: string | null;
  strain: string;
  room_id: string;
  growth_phase: string;
  planted_date: string;
  tagged_date: string;
  status: string;
}

export interface Harvest {
  id: string;
  name: string;
  strain: string;
  source_room_id: string;
  drying_room_id: string | null;
  wet_weight_g: number;
  status: string;
  started_at: string;
  finished_at: string | null;
}

export interface Package {
  id: string;
  harvest_id: string | null;
  source_package_id: string | null;
  process_method: string | null;
  process_yield_pct: number | null;
  item_name: string;
  weight_g: number;
  room_id: string;
  status: string;
  created_at: string;
}

export interface LabTest {
  id: string;
  package_id: string;
  lab_name: string;
  test_type: string;
  result: "pass" | "fail" | "pending";
  thc_pct: number | null;
  cbd_pct: number | null;
  notes: string;
  tested_at: string;
  recorded_at: string;
  recorded_by: string;
  coa_filename: string | null;
  coa_stored_path: string | null;
}

export interface ProcessPackageBody {
  item_name: string;
  weight_g: number;
  room_id: string;
  process_method: string;
  tag?: string;
  is_production_batch?: boolean;
  is_donation?: boolean;
  operator_id: string;
}

export interface CreateLabTestBody {
  lab_name: string;
  test_type: string;
  result: "pass" | "fail" | "pending";
  thc_pct?: number;
  cbd_pct?: number;
  notes?: string;
  tested_at: string;
  operator_id: string;
}

export interface HarvestWeightLog {
  id: number;
  harvest_id: string;
  stage: "wet" | "dry" | "cure";
  weight_g: number;
  room_id: string;
  recorded_at: string;
  actor: string;
}

export interface CreatePlantBatchBody {
  name: string;
  batch_type: "Seed" | "Clone";
  strain: string;
  room_id: string;
  planted_date: string;
  count: number;
  operator_id: string;
}

export interface TagPlantsBody {
  count: number;
  growth_phase: "Vegetative" | "Flowering";
  room_id?: string;
  operator_id: string;
}

export interface MovePlantBody {
  room_id: string;
  operator_id: string;
}

export interface DestroyPlantBody {
  weight_g: number;
  method: string;
  material: string;
  reason: string;
  note?: string;
  operator_id: string;
  pin?: string;
  witness_operator_id?: string;
}

export interface HarvestPlantBody {
  harvest_id: string;
  weight_g: number;
  operator_id: string;
}

export interface CreateHarvestBody {
  name: string;
  strain: string;
  source_room_id: string;
  drying_room_id?: string;
  operator_id: string;
}

export interface WeighHarvestBody {
  stage: "wet" | "dry" | "cure";
  weight_g: number;
  room_id: string;
  operator_id: string;
}

export interface PackageHarvestBody {
  item_name: string;
  weight_g: number;
  room_id: string;
  tag?: string;
  is_production_batch?: boolean;
  is_donation?: boolean;
  operator_id: string;
}

export interface WasteEvent {
  id: number;
  source_type: string;
  source_id: string;
  room_id: string;
  waste_type: string;
  method: string | null;
  material: string | null;
  reason: string | null;
  weight_g: number;
  note: string;
  occurred_at: string;
  recorded_at: string;
  reported_at: string | null;
  actor: string;
  witnessed_by: string | null;
  // Both null when the active state's deadline shape isn't a computable "report by X
  // after occurrence" date (e.g. a pre-destruction notice requirement) — see
  // compliance_deadlines.py. Null must not be read as "not overdue."
  reporting_deadline: string | null;
  overdue: boolean | null;
}

export interface Operator {
  id: string;
  name: string;
  has_pin: boolean;
}

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  room_id: string | null;
  details: Record<string, unknown>;
  occurred_at: string;
}

export interface ReconciliationRow {
  room_id: string;
  system_count: number;
  last_physical_count: number | null;
  last_counted_at: string | null;
  discrepancy: number | null;
  needs_recount: boolean;
  stale: boolean;
}

export type Confidence = "primary_source" | "secondary_source" | "could_not_verify";

export interface PlantLimit {
  count: number;
  unit: "per_person" | "per_residence" | "per_patient" | "per_caregiver";
  note: string;
}

export interface HomeGrowRules {
  recreational_allowed: boolean;
  recreational_limit: PlantLimit | null;
  medical_allowed: boolean;
  medical_limit: PlantLimit | null;
  extended_medical_available: boolean;
  extended_medical_limit: PlantLimit | null;
  extended_medical_note: string;
  caregiver_limit: PlantLimit | null;
  caregiver_max_patients: number | null;
  geographic_gate: string | null;
  confidence: Confidence;
  notes: string;
}

export interface PurchaseLimit {
  amount: number;
  unit:
    | "grams_flower_equivalent"
    | "grams_flower"
    | "grams_concentrate"
    | "mg_thc_edible"
    | "ounces_flower"
    | "grams_edible_product";
  period: "per_transaction" | "per_day" | "per_rolling_period";
  note: string;
}

export interface RetailRules {
  recreational_allowed: boolean;
  recreational_purchase_limits: PurchaseLimit[];
  recreational_min_age: number | null;
  medical_allowed: boolean;
  medical_purchase_limits: PurchaseLimit[];
  medical_min_age: number | null;
  id_verification_required: boolean | null;
  id_verification_note: string;
  pos_realtime_sync_required: boolean | null;
  pos_realtime_sync_note: string;
  confidence: Confidence;
  notes: string;
}

export interface StateComplianceRules {
  state_code: string;
  state_name: string;
  platform: "metrc" | "biotrack" | "leaf_data_systems" | "state_built" | "none" | "unknown";
  platform_confidence: Confidence;
  tagging_trigger_kind: "phase" | "size" | "immediate" | "no_trigger_found" | "unknown";
  tagging_trigger_value: string;
  tagging_trigger_confidence: Confidence;
  deadline_kind:
    | "hours_after_occurrence"
    | "business_days_after_occurrence"
    | "pre_destruction_notice_days"
    | "destroy_by_days_after_logging"
    | "no_deadline_found"
    | "unknown";
  deadline_value: number | null;
  deadline_confidence: Confidence;
  reconciliation_cadence_days: number | null;
  reconciliation_confidence: Confidence;
  testing_required_for_solvent_extracts: boolean | null;
  testing_confidence: Confidence;
  testing_note: string;
  home_grow: HomeGrowRules;
  retail: RetailRules;
  notes: string;
}

export interface StateRulesResponse {
  active: StateComplianceRules;
  explicitly_set: boolean;
  available: StateComplianceRules[];
}

export interface PinPolicy {
  require_operator_pins: boolean;
  operators_without_pin: number;
}
