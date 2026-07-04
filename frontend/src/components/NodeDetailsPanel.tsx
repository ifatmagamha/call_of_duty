import { Activity, Clock, MapPin, Package, Users } from "lucide-react";
import { ClinicUpdateForm } from "./ClinicUpdateForm";
import type { Clinic, ClinicUpdate, Warehouse } from "../types";

type NodeDetailsPanelProps = {
  clinic: Clinic | null;
  warehouse: Warehouse | null;
  loading: boolean;
  onClinicUpdate: (update: ClinicUpdate) => Promise<void>;
};

function formatHours(value: number | null) {
  return value === null ? "n/a" : `${value.toFixed(2)} h`;
}

export function NodeDetailsPanel({
  clinic,
  warehouse,
  loading,
  onClinicUpdate,
}: NodeDetailsPanelProps) {
  if (loading) {
    return <div className="panel-muted">Loading selected node...</div>;
  }

  if (!clinic && !warehouse) {
    return <div className="panel-muted">Select a marker on the map.</div>;
  }

  if (warehouse) {
    return (
      <section className="panel-section">
        <div>
          <p className="eyebrow">Warehouse</p>
          <h2 className="panel-title">{warehouse.name}</h2>
        </div>
        <dl className="metric-grid">
          <div>
            <dt>
              <Package size={15} /> Stock
            </dt>
            <dd>{warehouse.test_kits_stock}</dd>
          </div>
          <div>
            <dt>
              <MapPin size={15} /> Coordinates
            </dt>
            <dd>
              {warehouse.latitude.toFixed(4)}, {warehouse.longitude.toFixed(4)}
            </dd>
          </div>
        </dl>
      </section>
    );
  }

  if (!clinic) {
    return null;
  }

  return (
    <section className="panel-section">
      <div>
        <p className="eyebrow">Clinic</p>
        <div className="flex items-start justify-between gap-3">
          <h2 className="panel-title">{clinic.name}</h2>
          <span className={`risk-pill risk-${clinic.risk_level}`}>
            {clinic.risk_level}
          </span>
        </div>
      </div>

      <dl className="metric-grid">
        <div>
          <dt>
            <Package size={15} /> Kits
          </dt>
          <dd>{clinic.test_kits_available}</dd>
        </div>
        <div>
          <dt>
            <Users size={15} /> Waiting
          </dt>
          <dd>{clinic.people_waiting}</dd>
        </div>
        <div>
          <dt>
            <Activity size={15} /> Capacity
          </dt>
          <dd>{clinic.testing_capacity_per_hour}/h</dd>
        </div>
        <div>
          <dt>
            <Clock size={15} /> Operations
          </dt>
          <dd>{formatHours(clinic.operations_remaining_hours)}</dd>
        </div>
        <div>
          <dt>
            <Clock size={15} /> Queue
          </dt>
          <dd>{formatHours(clinic.queue_delay_hours)}</dd>
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
  );
}
