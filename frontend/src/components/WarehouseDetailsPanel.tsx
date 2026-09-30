import { MapPin, Package } from "lucide-react";
import type { Warehouse } from "../types";

type WarehouseDetailsPanelProps = {
  warehouse: Warehouse | null;
  loading: boolean;
};

export function WarehouseDetailsPanel({ warehouse, loading }: WarehouseDetailsPanelProps) {
  if (loading) {
    return <div className="panel-muted">Loading selected warehouse...</div>;
  }

  if (!warehouse) {
    return <div className="panel-muted">Select a warehouse on the map.</div>;
  }

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
