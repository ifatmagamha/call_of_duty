import { useEffect, useRef } from "react";
import L from "leaflet";
import type { Clinic, Selection, SupplyLink, Warehouse } from "../types";

type MapViewProps = {
  clinics: Clinic[];
  warehouses: Warehouse[];
  supplyLinks: SupplyLink[];
  selected: Selection | null;
  onSelect: (selection: Selection) => void;
};

const RISK_CLASS: Record<Clinic["risk_level"], string> = {
  normal: "marker-normal",
  medium: "marker-medium",
  high: "marker-high",
  critical: "marker-critical",
};

export function MapView({
  clinics,
  warehouses,
  supplyLinks,
  selected,
  onSelect,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = L.map(containerRef.current, {
      center: [-4.315, 15.3],
      zoom: 11,
      zoomControl: false,
    });

    L.control.zoom({ position: "bottomleft" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) {
      return;
    }

    layer.clearLayers();

    supplyLinks.forEach((link) => {
      const touchesSelection =
        selected?.id === link.source_id || selected?.id === link.target_id;
      const isWarehouseRoute = link.source_type === "warehouse";
      const line = L.polyline(
        [
          [link.source_latitude, link.source_longitude],
          [link.target_latitude, link.target_longitude],
        ],
        {
          color: isWarehouseRoute ? "#315b87" : "#1f6b59",
          dashArray: link.road_status === "slow" ? "8 7" : undefined,
          opacity: touchesSelection ? 0.95 : 0.34,
          weight: touchesSelection ? 4 : 2,
        },
      ).bindTooltip(
        `${link.source_name} -> ${link.target_name}: ${link.delivery_time_minutes} min, ${link.road_status}`,
      );
      line.addTo(layer);
    });

    clinics.forEach((clinic) => {
      const isSelected =
        selected?.type === "clinic" && selected.id === clinic.id;
      const marker = L.marker([clinic.latitude, clinic.longitude], {
        icon: L.divIcon({
          className: "",
          html: `<span class="clinic-marker ${RISK_CLASS[clinic.risk_level]} ${
            isSelected ? "marker-selected" : ""
          }"></span>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        }),
      }).bindTooltip(clinic.name);
      marker.on("click", () => onSelect({ type: "clinic", id: clinic.id }));
      marker.addTo(layer);
    });

    warehouses.forEach((warehouse) => {
      const isSelected =
        selected?.type === "warehouse" && selected.id === warehouse.id;
      const marker = L.marker([warehouse.latitude, warehouse.longitude], {
        icon: L.divIcon({
          className: "",
          html: `<span class="warehouse-marker ${
            isSelected ? "marker-selected" : ""
          }"><span>WH</span><small>${warehouse.test_kits_stock}</small></span>`,
          iconSize: [46, 38],
          iconAnchor: [23, 19],
        }),
      }).bindTooltip(warehouse.name);
      marker.on("click", () =>
        onSelect({ type: "warehouse", id: warehouse.id }),
      );
      marker.addTo(layer);
    });
  }, [clinics, warehouses, supplyLinks, selected, onSelect]);

  return (
    <div className="relative h-full min-h-[420px] w-full">
      <div ref={containerRef} className="h-full min-h-[420px] w-full" />
      <div className="map-legend">
        <span>
          <i className="legend-clinic"></i> Clinic risk
        </span>
        <span>
          <i className="legend-warehouse"></i> Warehouse
        </span>
        <span>
          <i className="legend-route warehouse-route"></i> Warehouse route
        </span>
      </div>
    </div>
  );
}
