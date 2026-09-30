import { useCallback, useEffect, useMemo, useState } from "react";
import { Radio, RotateCcw, X } from "lucide-react";
import { api } from "./api/client";
import { ClinicSiteModal } from "./components/ClinicSiteModal";
import { MapView } from "./components/MapView";
import { MediaIngestionPanel } from "./components/MediaIngestionPanel";
import { ObservationReviewPanel } from "./components/ObservationReviewPanel";
import { PriorityActionsPanel } from "./components/PriorityActionsPanel";
import { SituationBriefingPanel } from "./components/SituationBriefingPanel";
import { TimelineList } from "./components/TimelineList";
import { WarehouseDetailsPanel } from "./components/WarehouseDetailsPanel";
import type {
  AgentRecommendation,
  Clinic,
  ClinicUpdate,
  Selection,
  SupplyLink,
  TimelineEntry,
  Transfer,
  Warehouse,
} from "./types";

// ponytail: 5 s polling; switch to SSE/websockets when clinic count or users grow.
const REFRESH_MS = 5000;
type SideTab = "actions" | "activity" | "report" | "review" | "ask";
const SIDE_TABS: { id: SideTab; label: string }[] = [
  { id: "actions", label: "Actions" },
  { id: "activity", label: "Activity" },
  { id: "report", label: "Report" },
  { id: "review", label: "Review" },
  { id: "ask", label: "Ask" },
];

export default function App() {
  const [clinics, setClinics] = useState<Clinic[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [supplyLinks, setSupplyLinks] = useState<SupplyLink[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [isSiteModalOpen, setIsSiteModalOpen] = useState(false);
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
  const [region, setRegion] = useState("all");
  const [sideTab, setSideTab] = useState<SideTab>("actions");
  const [actions, setActions] = useState<AgentRecommendation[]>([]);
  const [activity, setActivity] = useState<TimelineEntry[]>([]);
  const [clinicTimeline, setClinicTimeline] = useState<TimelineEntry[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [busyClinicId, setBusyClinicId] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<Date | null>(null);

  const regions = useMemo(
    () => [...new Set(clinics.map((clinic) => clinic.region))].sort(),
    [clinics],
  );
  const visibleClinics = useMemo(
    () => (region === "all" ? clinics : clinics.filter((c) => c.region === region)),
    [clinics, region],
  );
  const visibleIds = useMemo(() => new Set(visibleClinics.map((c) => c.id)), [visibleClinics]);
  const kpis = useMemo(() => ({
    critical: visibleClinics.filter((c) => c.risk_level === "critical").length,
    high: visibleClinics.filter((c) => c.risk_level === "high").length,
    waiting: visibleClinics.reduce((sum, c) => sum + c.people_waiting, 0),
    kits: visibleClinics.reduce((sum, c) => sum + c.test_kits_available, 0),
    enRoute: transfers.filter((t) => visibleIds.has(t.target_clinic_id)).length,
  }), [visibleClinics, transfers, visibleIds]);

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
    const [actionList, activityList, pending] = await Promise.all([
      api.getActions(),
      api.getTimeline(undefined, 40),
      api.getObservations({ status: "pending_review", limit: 200 }),
    ]);
    setActions(actionList);
    setActivity(activityList);
    setPendingCount(pending.length);
    setLastSync(new Date());
  }, []);

  // Reloads everything the clinic modal shows, without loading flags (no flicker).
  const refreshClinic = useCallback(async (clinicId: string) => {
    const [clinic, agent, timeline] = await Promise.all([
      api.getClinic(clinicId),
      api.getAgentRecommendation(clinicId),
      api.getTimeline(clinicId),
    ]);
    setSelectedClinic(clinic);
    setRecommendation(agent);
    setClinicTimeline(timeline);
  }, []);

  // Live refresh: collections always, the open clinic silently (no loading flicker).
  useEffect(() => {
    const timer = window.setInterval(() => {
      loadCollections().catch(() => undefined);
      if (selected?.type === "clinic" && isSiteModalOpen) {
        refreshClinic(selected.id).catch(() => undefined);
      }
    }, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [loadCollections, refreshClinic, selected, isSiteModalOpen]);

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
      setClinicTimeline([]);
      api.getTimeline(selected.id).then(setClinicTimeline).catch(() => undefined);
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

  useEffect(() => {
    if (!isSiteModalOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsSiteModalOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSiteModalOpen]);

  function handleSelectSite(selection: Selection) {
    setSelected(selection);
    setIsSiteModalOpen(true);
  }

  async function handleResetDemoData() {
    setError(null);
    setActionMessage(null);
    await api.resetDemoData();
    await loadCollections();
    setSelected({ type: "clinic", id: "clinic-b" });
    setIsSiteModalOpen(true);
  }

  function openClinic(clinicId: string) {
    handleSelectSite({ type: "clinic", id: clinicId });
  }

  async function handleApproveAction(action: AgentRecommendation) {
    const best = action.options[0];
    if (!best) return;
    const confirmed = window.confirm(
      `Dispatch ${best.recommended_transfer_quantity} kits from ${best.source_name} to ${action.clinic}?`,
    );
    if (!confirmed) return;
    setBusyClinicId(action.clinic_id);
    setError(null);
    try {
      await api.createTransfer(action.clinic_id, best.source_id);
      await loadCollections();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to dispatch transfer.");
    } finally {
      setBusyClinicId(null);
    }
  }

  async function handleCompleteTransfer(transfer: Transfer) {
    setError(null);
    try {
      await api.completeTransfer(transfer.id);
      await Promise.all([loadCollections(), refreshClinic(transfer.target_clinic_id)]);
      setActionMessage(`${transfer.quantity} kits delivered to ${transfer.target_clinic_name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to complete transfer.");
    }
  }

  async function handleObservationApplied() {
    await loadCollections();
    setObservationRefreshKey((value) => value + 1);
    if (selected?.type === "clinic") await refreshClinic(selected.id);
  }

  async function handleClinicUpdate(update: ClinicUpdate) {
    if (!selectedClinic) {
      return;
    }
    setError(null);
    setActionMessage(null);
    await api.updateClinic(selectedClinic.id, update);
    await Promise.all([loadCollections(), refreshClinic(selectedClinic.id)]);
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
      await Promise.all([loadCollections(), refreshClinic(selectedClinic.id)]);
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
            <p className="eyebrow">Epidemic operations · clinic resources</p>
            <h1>Call of Duty</h1>
          </div>
          <div className="topbar-controls">
            <label className="field-label region-select">Region
              <select className="number-input" value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="all">All regions</option>
                {regions.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </label>
            <span className="live-dot" title={lastSync ? `Last sync ${lastSync.toLocaleTimeString()}` : "Connecting"}>
              <Radio size={14} /> {lastSync ? "Live" : "…"}
            </span>
            <button className="secondary-button" onClick={handleResetDemoData}>
              <RotateCcw size={16} />
              Reset demo
            </button>
          </div>
        </div>
        <dl className="kpi-strip">
          <div className="kpi-critical"><dt>Critical</dt><dd>{kpis.critical}</dd></div>
          <div className="kpi-high"><dt>High risk</dt><dd>{kpis.high}</dd></div>
          <div><dt>People waiting</dt><dd>{kpis.waiting}</dd></div>
          <div><dt>Test kits on site</dt><dd>{kpis.kits}</dd></div>
          <div><dt>Transfers en route</dt><dd>{kpis.enRoute}</dd></div>
          <div><dt>Awaiting review</dt><dd>{pendingCount}</dd></div>
        </dl>
        {error && <div className="error-banner">{error}</div>}
        <MapView
          clinics={visibleClinics}
          warehouses={warehouses}
          supplyLinks={supplyLinks}
          selected={selected}
          onSelect={handleSelectSite}
        />
      </section>

      <aside className="side-panel">
        <nav className="side-tabs" role="tablist">
          {SIDE_TABS.map((tab) => (
            <button key={tab.id} type="button" role="tab" aria-selected={sideTab === tab.id}
              className={sideTab === tab.id ? "side-tab active" : "side-tab"}
              onClick={() => setSideTab(tab.id)}>
              {tab.label}
              {tab.id === "actions" && actions.length > 0 && <span className="tab-badge">{actions.length}</span>}
              {tab.id === "review" && pendingCount > 0 && <span className="tab-badge">{pendingCount}</span>}
            </button>
          ))}
        </nav>
        {sideTab === "actions" && (
          <section className="panel-section">
            <div><p className="eyebrow">Decide fast</p><h2 className="panel-title">Priority actions</h2></div>
            <PriorityActionsPanel
              actions={actions.filter((a) => visibleIds.has(a.clinic_id))}
              transfers={transfers}
              busyClinicId={busyClinicId}
              onApprove={handleApproveAction}
              onOpen={openClinic}
            />
          </section>
        )}
        {sideTab === "activity" && (
          <section className="panel-section">
            <div><p className="eyebrow">Live feed</p><h2 className="panel-title">What is happening</h2></div>
            <TimelineList
              entries={activity.filter((e) => visibleIds.has(e.clinic_id))}
              showClinic
              onSelectClinic={openClinic}
            />
          </section>
        )}
        {sideTab === "report" && (
          <MediaIngestionPanel clinics={clinics} onApplied={handleObservationApplied} />
        )}
        {sideTab === "review" && (
          <ObservationReviewPanel refreshKey={observationRefreshKey} onApplied={handleObservationApplied} />
        )}
        {sideTab === "ask" && <SituationBriefingPanel />}
      </aside>

      {isSiteModalOpen && selected && (
        <div
          aria-modal="true"
          aria-labelledby="site-modal-title"
          className="site-modal-overlay"
          role="dialog"
          onClick={() => setIsSiteModalOpen(false)}
        >
          <div
            className="site-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="site-modal-header">
              <div>
                <p className="eyebrow">Map site</p>
                <h2 className="panel-title" id="site-modal-title">
                  {selected.type === "clinic" ? "Clinic details" : "Warehouse details"}
                </h2>
              </div>
              <button
                className="modal-close-button"
                onClick={() => setIsSiteModalOpen(false)}
                type="button"
              >
                <X size={18} />
                Close
              </button>
            </div>
            <div className="site-modal-body">
              {selected.type === "clinic" ? (
                <ClinicSiteModal
                  clinic={selectedClinic ?? selectedClinicFromList}
                  recommendation={recommendation}
                  transfers={transfers}
                  timeline={clinicTimeline}
                  loading={loadingNode}
                  loadingAgent={loadingAgent}
                  validatingSourceId={validatingSourceId}
                  actionMessage={actionMessage}
                  onClinicUpdate={handleClinicUpdate}
                  onValidateTransfer={handleValidateTransfer}
                  onRejectTransfer={handleRejectTransfer}
                  onCompleteTransfer={handleCompleteTransfer}
                />
              ) : (
                <WarehouseDetailsPanel
                  warehouse={selectedWarehouse}
                  loading={loadingNode}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
