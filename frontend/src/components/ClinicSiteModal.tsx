import { Activity, Clock, MapPin, Package, Users } from "lucide-react";
import queueImage from "../assets/clinic-queue.png";
import type {
  AgentRecommendation,
  Clinic,
  ClinicUpdate,
  ResupplyOption,
  Transfer,
} from "../types";
import { AgentReasoningPanel } from "./AgentReasoningPanel";
import { ClinicUpdateForm } from "./ClinicUpdateForm";

type ClinicSiteModalProps = {
  clinic: Clinic | null;
  recommendation: AgentRecommendation | null;
  transfers: Transfer[];
  loading: boolean;
  loadingAgent: boolean;
  validatingSourceId: string | null;
  actionMessage: string | null;
  onClinicUpdate: (update: ClinicUpdate) => Promise<void>;
  onValidateTransfer: (option: ResupplyOption) => Promise<void>;
  onRejectTransfer: () => void;
};

function formatHours(value: number | null) {
  return value === null ? "n/a" : `${value.toFixed(2)} h`;
}

export function ClinicSiteModal({
  clinic,
  recommendation,
  transfers,
  loading,
  loadingAgent,
  validatingSourceId,
  actionMessage,
  onClinicUpdate,
  onValidateTransfer,
  onRejectTransfer,
}: ClinicSiteModalProps) {
  if (loading) {
    return <div className="panel-muted">Loading selected clinic...</div>;
  }

  if (!clinic) {
    return <div className="panel-muted">Select a clinic marker on the map.</div>;
  }

  const clinicTransfers = transfers.filter(
    (transfer) => transfer.target_clinic_id === clinic.id,
  );
  const ongoingTransfer = clinicTransfers[0] ?? null;

  return (
    <div className="clinic-site-layout">
      <section className="clinic-site-left">
        <figure className="clinic-queue-figure">
          <img src={queueImage} alt="People waiting in line outside a clinic" />
        </figure>

        <div className="clinic-indicator-header">
          <div>
            <p className="eyebrow">Indicators</p>
            <h3>{clinic.name}</h3>
          </div>
          <span className={`risk-pill risk-${clinic.risk_level}`}>
            {clinic.risk_level}
          </span>
        </div>

        <dl className="metric-grid">
          <div>
            <dt>
              <Users size={15} /> Waiting
            </dt>
            <dd>{clinic.people_waiting}</dd>
          </div>
          <div>
            <dt>
              <Package size={15} /> Kits
            </dt>
            <dd>{clinic.test_kits_available}</dd>
          </div>
          <div>
            <dt>
              <Activity size={15} /> Capacity
            </dt>
            <dd>{clinic.testing_capacity_per_hour}/h</dd>
          </div>
          <div>
            <dt>
              <Clock size={15} /> Queue
            </dt>
            <dd>{formatHours(clinic.queue_delay_hours)}</dd>
          </div>
          <div>
            <dt>
              <Clock size={15} /> Operations
            </dt>
            <dd>{formatHours(clinic.operations_remaining_hours)}</dd>
          </div>
          <div>
            <dt>
              <MapPin size={15} /> Coordinates
            </dt>
            <dd>
              {clinic.latitude.toFixed(4)}, {clinic.longitude.toFixed(4)}
            </dd>
          </div>
        </dl>

        <ClinicUpdateForm clinic={clinic} onSubmit={onClinicUpdate} />
      </section>

      <section className="clinic-site-right">
        <div className="site-situation-card">
          <p className="eyebrow">What is happening</p>
          <h3>
            {recommendation?.recommendation ??
              `${clinic.name} is currently ${clinic.risk_level} risk.`}
          </h3>
          <p>
            {clinic.people_waiting} people are waiting, with{" "}
            {formatHours(clinic.queue_delay_hours)} queue delay and{" "}
            {formatHours(clinic.operations_remaining_hours)} of operations
            remaining.
          </p>
          {ongoingTransfer && (
            <div className="ongoing-transfer-banner">
              <span className="transfer-status">{ongoingTransfer.status}</span>
              <p>
                {ongoingTransfer.quantity} kits are reserved from{" "}
                {ongoingTransfer.source_name}; ETA{" "}
                {ongoingTransfer.delivery_time_minutes} minutes on a{" "}
                {ongoingTransfer.road_status} route.
              </p>
            </div>
          )}
        </div>

        <AgentReasoningPanel
          recommendation={recommendation}
          transfers={clinicTransfers}
          loading={loadingAgent}
          validatingSourceId={validatingSourceId}
          actionMessage={actionMessage}
          onValidateTransfer={onValidateTransfer}
          onRejectTransfer={onRejectTransfer}
        />
      </section>
    </div>
  );
}
