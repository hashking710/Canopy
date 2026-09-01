from datetime import date, datetime

from pydantic import BaseModel, Field


class CreatePlantBatchRequest(BaseModel):
    name: str
    batch_type: str  # "Seed" | "Clone"
    strain: str
    # Optional link to the genetics registry (Strain, see compliance_models.py) —
    # additive on top of the free-text strain field above, not a replacement for it.
    strain_id: str | None = None
    room_id: str
    planted_date: date
    count: int = Field(gt=0)
    operator_id: str


class TagPlantsRequest(BaseModel):
    count: int = Field(gt=0)
    growth_phase: str = "Vegetative"  # "Vegetative" | "Flowering"
    room_id: str | None = None  # defaults to the batch's room
    operator_id: str


class MovePlantRequest(BaseModel):
    room_id: str
    operator_id: str


class DestroyPlantRequest(BaseModel):
    weight_g: float = Field(gt=0)
    method: str = "Compost"
    material: str = "Soil"
    reason: str = "Contamination"
    note: str = ""
    operator_id: str
    pin: str | None = None  # required if the operator has one configured
    witness_operator_id: str | None = None  # optional second sign-off, recommended for destruction


class HarvestPlantRequest(BaseModel):
    harvest_id: str
    weight_g: float = Field(gt=0)
    operator_id: str


class CreateHarvestRequest(BaseModel):
    name: str
    strain: str
    strain_id: str | None = None
    source_room_id: str
    drying_room_id: str | None = None
    operator_id: str


class WeighHarvestRequest(BaseModel):
    stage: str  # "wet" | "dry" | "cure"
    weight_g: float = Field(gt=0)
    room_id: str
    operator_id: str


class FinishHarvestRequest(BaseModel):
    operator_id: str


class PackageHarvestRequest(BaseModel):
    item_name: str
    weight_g: float = Field(gt=0)
    room_id: str
    tag: str | None = None
    is_production_batch: bool = False
    is_donation: bool = False
    operator_id: str


class LogWasteRequest(BaseModel):
    source_type: str  # "plant" | "plant_batch" | "harvest" | "package"
    source_id: str
    room_id: str
    waste_type: str
    method: str | None = None
    material: str | None = None
    reason: str | None = None
    weight_g: float = Field(gt=0)
    note: str = ""
    occurred_at: datetime | None = None
    plant_count: int = 1  # only meaningful when source_type == "plant_batch"
    operator_id: str
    pin: str | None = None
    witness_operator_id: str | None = None


class RecordPhysicalCountRequest(BaseModel):
    room_id: str
    counted_value: int = Field(ge=0)  # a room legitimately can have zero plants
    note: str = ""
    operator_id: str


class SetComplianceStateRequest(BaseModel):
    state_code: str  # validated against the real registry in services/facility_state.py
    operator_id: str


class UpdatePackageStatusRequest(BaseModel):
    status: str  # "active" | "sold" | "destroyed" | "transferred" | "processed"
    operator_id: str


class ProcessPackageRequest(BaseModel):
    item_name: str
    weight_g: float = Field(gt=0)
    room_id: str
    process_method: str  # e.g. "BHO Extraction", "CO2 Extraction", "Winterization", "Short-Path Distillation"
    tag: str | None = None
    is_production_batch: bool = False
    is_donation: bool = False
    operator_id: str


class CreateLabTestRequest(BaseModel):
    lab_name: str
    test_type: str  # "residual_solvents" | "potency" | "microbial" | "pesticides" | "heavy_metals" | "other"
    result: str  # "pass" | "fail" | "pending"
    thc_pct: float | None = None
    cbd_pct: float | None = None
    notes: str = ""
    tested_at: date
    operator_id: str
