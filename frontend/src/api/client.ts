import type {
  AgentRecommendation,
  Clinic,
  ClinicUpdate,
  SupplyLink,
  Transfer,
  Warehouse,
  AudioIngestionResponse,
  ImageIngestionResponse,
  Observation,
  ObservationSourceType,
  ObservationStatus,
  SituationBriefing,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  resetDemoData: () =>
    request<{ status: string; clinics: number; warehouses: number }>(
      "/admin/reset-demo-data",
      { method: "POST" },
    ),
  getClinics: () => request<Clinic[]>("/clinics"),
  getClinic: (clinicId: string) => request<Clinic>(`/clinics/${clinicId}`),
  updateClinic: (clinicId: string, update: ClinicUpdate) =>
    request<Clinic>(`/clinics/${clinicId}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    }),
  getWarehouses: () => request<Warehouse[]>("/warehouses"),
  getSupplyLinks: () => request<SupplyLink[]>("/supply-links"),
  getTransfers: (status = "ongoing") =>
    request<Transfer[]>(`/transfers?status=${encodeURIComponent(status)}`),
  createTransfer: (clinicId: string, sourceId: string) =>
    request<Transfer>(`/clinics/${clinicId}/transfers`, {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId }),
    }),
  getWarehouse: (warehouseId: string) =>
    request<Warehouse>(`/warehouses/${warehouseId}`),
  getAgentRecommendation: (clinicId: string) =>
    request<AgentRecommendation>(
      `/clinics/${clinicId}/agent-recommendation`,
    ),
  ingestImage: (file: File, clinicHint?: string) => {
    const body = new FormData();
    body.append("file", file);
    if (clinicHint) body.append("clinic_hint", clinicHint);
    return request<ImageIngestionResponse>("/ingestion/image", { method: "POST", body });
  },
  ingestAudio: (file: File, clinicHint?: string) => {
    const body = new FormData();
    body.append("file", file);
    if (clinicHint) body.append("clinic_hint", clinicHint);
    return request<AudioIngestionResponse>("/ingestion/audio", { method: "POST", body });
  },
  getObservations: (filters: {
    status?: ObservationStatus;
    clinicId?: string;
    sourceType?: ObservationSourceType;
    limit?: number;
  } = {}) => {
    const query = new URLSearchParams();
    if (filters.status) query.set("status", filters.status);
    if (filters.clinicId) query.set("clinic_id", filters.clinicId);
    if (filters.sourceType) query.set("source_type", filters.sourceType);
    if (filters.limit) query.set("limit", String(filters.limit));
    return request<Observation[]>(`/observations?${query}`);
  },
  applyObservation: (id: string) =>
    request<Observation>(`/observations/${id}/apply`, { method: "POST" }),
  rejectObservation: (id: string) =>
    request<Observation>(`/observations/${id}/reject`, { method: "POST" }),
  generateBriefing: (windowHours = 24) =>
    request<SituationBriefing>("/briefings/generate", {
      method: "POST",
      body: JSON.stringify({ window_hours: windowHours }),
    }),
};
