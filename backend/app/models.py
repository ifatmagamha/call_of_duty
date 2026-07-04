from typing import Literal, Optional

from pydantic import BaseModel, Field


RiskLevel = Literal["normal", "medium", "high", "critical"]
RoadStatus = Literal["open", "slow", "blocked", "unknown"]
SourceType = Literal["warehouse", "clinic"]
TransferStatus = Literal["ongoing", "completed", "cancelled"]


class ClinicBase(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    test_kits_available: int = Field(ge=0)
    people_waiting: int = Field(ge=0)
    nurses_available: int = Field(ge=0)
    threshold_min_kits: int = Field(ge=0)


class Clinic(ClinicBase):
    testing_capacity_per_hour: int
    queue_delay_hours: Optional[float]
    operations_remaining_hours: Optional[float]
    risk_level: RiskLevel
    last_updated_at: str
    last_computed_at: str


class ClinicUpdate(BaseModel):
    test_kits_available: Optional[int] = Field(default=None, ge=0)
    people_waiting: Optional[int] = Field(default=None, ge=0)
    nurses_available: Optional[int] = Field(default=None, ge=0)
    threshold_min_kits: Optional[int] = Field(default=None, ge=0)


class Warehouse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    test_kits_stock: int = Field(ge=0)
    last_updated_at: str


class WarehouseUpdate(BaseModel):
    test_kits_stock: int = Field(ge=0)


class ResupplyOption(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    available_stock: int
    delivery_time_minutes: int
    road_status: RoadStatus
    recommended_transfer_quantity: int
    supplier_remaining_stock_after_transfer: int
    supplier_operations_remaining_after_transfer: Optional[float]
    is_safe_for_supplier: bool
    can_fully_supply: bool
    rank: int
    reason: str


class LLMAgentNote(BaseModel):
    available: bool
    provider: str
    model: Optional[str] = None
    reasoning_summary: list[str] = Field(default_factory=list)
    proposed_action: str
    data_sources: list[str] = Field(default_factory=list)


class AgentRecommendation(BaseModel):
    clinic_id: str
    clinic: str
    status: RiskLevel
    reasoning: list[str]
    recommendation: str
    options: list[ResupplyOption]
    llm_used: bool = False
    llm_provider: str = "deterministic"
    llm_model: Optional[str] = None
    data_sources: list[str] = Field(default_factory=list)
    llm_agent: Optional[LLMAgentNote] = None


class SupplyLink(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    source_latitude: float
    source_longitude: float
    target_id: str
    target_name: str
    target_type: Literal["clinic"]
    target_latitude: float
    target_longitude: float
    delivery_time_minutes: int
    road_status: RoadStatus
    max_transfer_kits: Optional[int] = None


class TransferCreate(BaseModel):
    source_id: str


class Transfer(BaseModel):
    id: str
    status: TransferStatus
    source_id: str
    source_name: str
    target_clinic_id: str
    target_clinic_name: str
    quantity: int = Field(gt=0)
    delivery_time_minutes: int
    road_status: RoadStatus
    created_at: str
    updated_at: str


class Alert(BaseModel):
    clinic_id: str
    clinic: str
    risk_level: RiskLevel
    operations_remaining_hours: Optional[float]
    queue_delay_hours: Optional[float]
    reason: str
