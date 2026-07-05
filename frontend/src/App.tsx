import { useCallback, useEffect, useMemo, useState } from "react";
import { RotateCcw } from "lucide-react";
import { api } from "./api/client";
import { AgentReasoningPanel } from "./components/AgentReasoningPanel";
import { MapView } from "./components/MapView";
import { NodeDetailsPanel } from "./components/NodeDetailsPanel";
import { MediaIngestionPanel } from "./components/MediaIngestionPanel";
import { ObservationReviewPanel } from "./components/ObservationReviewPanel";
import { SituationBriefingPanel } from "./components/SituationBriefingPanel";
import type {
  AgentRecommendation,
  Clinic,
  ClinicUpdate,
  Selection,
  SupplyLink,
  Transfer,
  Warehouse,
} from "./types";

export default function App() {
  const [clinics, setClinics] = useState<Clinic[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [supplyLinks, setSupplyLinks] = useState<SupplyLink[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [selectedClinic, setSelectedClinic] = useState<Clinic | null>(null);
  const [selectedWarehouse, setSelectedWarehouse] = useState<Warehouse | null>(
    null,
  );
  const [recommendation, setRecommendation] =
    useState<AgentRecommendation | null>(null);
  const [loadingNode, setLoadingNode] = useState(false);
  const [loadingAgent, setLoadingAgent] = useState(false);
  const [validatingSourceId, setValidatingSourceId] = useState<string | null>(
    null,
  );
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [observationRefreshKey, setObservationRefreshKey] = useState(0);

  const selectedClinicFromList = useMemo(
    () =>
      selected?.type === "clinic"
        ? clinics.find((clinic) => clinic.id === selected.id) ?? null
        : null,
    [clinics, selected],
  );

  const loadCollections = useCallback(async () => {
    const [clinicList, warehouseList, linkList, transferList] = await Promise.all([
      api.getClinics(),
      api.getWarehouses(),
      api.getSupplyLinks(),
      api.getTransfers(),
    ]);
    setClinics(clinicList);
    setWarehouses(warehouseList);
    setSupplyLinks(linkList);
    setTransfers(transferList);
  }, []);

  useEffect(() => {
    loadCollections().catch((err) => {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load operational data.",
      );
    });
  }, [loadCollections]);

  useEffect(() => {
    if (!selected) {
      setSelectedClinic(null);
      setSelectedWarehouse(null);
      setRecommendation(null);
      return;
    }

    setError(null);
    setLoadingNode(true);
    setRecommendation(null);
    setActionMessage(null);

    if (selected.type === "clinic") {
      api
        .getClinic(selected.id)
        .then((clinic) => {
          setSelectedClinic(clinic);
          setSelectedWarehouse(null);
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoadingNode(false));

      setLoadingAgent(true);
      api
        .getAgentRecommendation(selected.id)
        .then(setRecommendation)
        .catch((err) => setError(err.message))
        .finally(() => setLoadingAgent(false));
      return;
    }

    api
      .getWarehouse(selected.id)
      .then((warehouse) => {
        setSelectedWarehouse(warehouse);
        setSelectedClinic(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingNode(false));
    setLoadingAgent(false);
  }, [selected]);

  async function handleResetDemoData() {
    setError(null);
    setActionMessage(null);
    await api.resetDemoData();
    await loadCollections();
    setSelected({ type: "clinic", id: "clinic-b" });
  }

  async function handleObservationApplied() {
    await loadCollections();
    setObservationRefreshKey((value) => value + 1);
    if (selected?.type === "clinic") {
      const [clinic, agent] = await Promise.all([
        api.getClinic(selected.id), api.getAgentRecommendation(selected.id),
      ]);
      setSelectedClinic(clinic); setRecommendation(agent);
    }
  }

  async function handleClinicUpdate(update: ClinicUpdate) {
    if (!selectedClinic) {
      return;
    }
    setError(null);
    setActionMessage(null);
    const clinic = await api.updateClinic(selectedClinic.id, update);
    setSelectedClinic(clinic);
    const [clinicList, agent] = await Promise.all([
      api.getClinics(),
      api.getAgentRecommendation(clinic.id),
    ]);
    setClinics(clinicList);
    setRecommendation(agent);
  }

  async function handleValidateTransfer(option: AgentRecommendation["options"][number]) {
    if (!selectedClinic) {
      return;
    }
    const confirmed = window.confirm(
      `Validate option ${option.rank}: reserve ${option.recommended_transfer_quantity} kits from ${option.source_name}?`,
    );
    if (!confirmed) {
      return;
    }

    setError(null);
    setActionMessage(
      `Agent selected option ${option.rank}: ${option.source_name}. Reasoning: ${option.reason}`,
    );
    setValidatingSourceId(option.source_id);
    try {
      const transfer = await api.createTransfer(selectedClinic.id, option.source_id);
      const [clinic, clinicList, warehouseList, transferList, agent] =
        await Promise.all([
          api.getClinic(selectedClinic.id),
          api.getClinics(),
          api.getWarehouses(),
          api.getTransfers(),
          api.getAgentRecommendation(selectedClinic.id),
        ]);
      setSelectedClinic(clinic);
      setClinics(clinicList);
      setWarehouses(warehouseList);
      setTransfers(transferList);
      setRecommendation(agent);
      setActionMessage(
        `Validated option ${option.rank}. Reserved ${transfer.quantity} kits from ${transfer.source_name}; transfer is now ongoing to ${transfer.target_clinic_name}.`,
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unable to validate transfer.";
      setError(message);
      setActionMessage(
        `Validation failed for option ${option.rank}. Reasoning: ${message}`,
      );
    } finally {
      setValidatingSourceId(null);
    }
  }

  function handleRejectTransfer() {
    setActionMessage(
      "No proposal was validated. The agent launched no transfer, so warehouse stock remains unchanged.",
    );
  }

  return (
    <main className="app-shell">
      <section className="map-panel">
        <div className="topbar">
          <div>
            <p className="eyebrow">Kinshasa response map</p>
            <h1>Ebola Test Kit Resupply</h1>
          </div>
          <button className="secondary-button" onClick={handleResetDemoData}>
            <RotateCcw size={16} />
            Reset demo
          </button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        <MapView
          clinics={clinics}
          warehouses={warehouses}
          supplyLinks={supplyLinks}
          selected={selected}
          onSelect={setSelected}
        />
      </section>

      <aside className="side-panel">
        <MediaIngestionPanel clinics={clinics} onApplied={handleObservationApplied} />
        <ObservationReviewPanel refreshKey={observationRefreshKey} onApplied={handleObservationApplied} />
        <SituationBriefingPanel />
        <NodeDetailsPanel
          clinic={selectedClinic ?? selectedClinicFromList}
          warehouse={selectedWarehouse}
          loading={loadingNode}
          onClinicUpdate={handleClinicUpdate}
        />
        <AgentReasoningPanel
          recommendation={recommendation}
          transfers={transfers}
          loading={loadingAgent}
          validatingSourceId={validatingSourceId}
          actionMessage={actionMessage}
          onValidateTransfer={handleValidateTransfer}
          onRejectTransfer={handleRejectTransfer}
        />
      </aside>
    </main>
  );
}
