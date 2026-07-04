export type RiskLevel = "normal" | "medium" | "high" | "critical";

export type Clinic = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  test_kits_available: number;
  people_waiting: number;
  nurses_available: number;
  threshold_min_kits: number;
  testing_capacity_per_hour: number;
  queue_delay_hours: number | null;
  operations_remaining_hours: number | null;
  risk_level: RiskLevel;
  last_updated_at: string;
  last_computed_at: string;
};

export type Warehouse = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  test_kits_stock: number;
  last_updated_at: string;
};

export type SupplyLink = {
  source_id: string;
  source_name: string;
  source_type: "warehouse" | "clinic";
  source_latitude: number;
  source_longitude: number;
  target_id: string;
  target_name: string;
  target_type: "clinic";
  target_latitude: number;
  target_longitude: number;
  delivery_time_minutes: number;
  road_status: "open" | "slow" | "blocked" | "unknown";
  max_transfer_kits: number | null;
};

export type ResupplyOption = {
  source_id: string;
  source_name: string;
  source_type: "warehouse" | "clinic";
  available_stock: number;
  delivery_time_minutes: number;
  road_status: "open" | "slow" | "blocked" | "unknown";
  recommended_transfer_quantity: number;
  supplier_remaining_stock_after_transfer: number;
  supplier_operations_remaining_after_transfer: number | null;
  is_safe_for_supplier: boolean;
  can_fully_supply: boolean;
  rank: number;
  reason: string;
};

export type LLMAgentNote = {
  available: boolean;
  provider: string;
  model: string | null;
  reasoning_summary: string[];
  proposed_action: string;
  data_sources: string[];
};

export type AgentRecommendation = {
  clinic_id: string;
  clinic: string;
  status: RiskLevel;
  reasoning: string[];
  recommendation: string;
  options: ResupplyOption[];
  llm_used: boolean;
  llm_provider: string;
  llm_model: string | null;
  data_sources: string[];
  llm_agent: LLMAgentNote | null;
};

export type Transfer = {
  id: string;
  status: "ongoing" | "completed" | "cancelled";
  source_id: string;
  source_name: string;
  target_clinic_id: string;
  target_clinic_name: string;
  quantity: number;
  delivery_time_minutes: number;
  road_status: "open" | "slow" | "blocked" | "unknown";
  created_at: string;
  updated_at: string;
};

export type Selection =
  | { type: "clinic"; id: string }
  | { type: "warehouse"; id: string };

export type ClinicUpdate = {
  test_kits_available?: number;
  people_waiting?: number;
  nurses_available?: number;
  threshold_min_kits?: number;
};
