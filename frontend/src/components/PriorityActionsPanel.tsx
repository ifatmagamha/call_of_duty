import { AlertTriangle, Truck } from "lucide-react";
import type { AgentRecommendation, Transfer } from "../types";

type Props = {
  actions: AgentRecommendation[];
  transfers: Transfer[];
  busyClinicId: string | null;
  onApprove: (action: AgentRecommendation) => Promise<void>;
  onOpen: (clinicId: string) => void;
};

export function PriorityActionsPanel({ actions, transfers, busyClinicId, onApprove, onOpen }: Props) {
  if (actions.length === 0) {
    return <p className="panel-muted">No clinic needs action right now.</p>;
  }
  return (
    <div className="action-list">
      {actions.map((action) => {
        const best = action.options[0];
        const enRoute = transfers.some((t) => t.target_clinic_id === action.clinic_id);
        return (
          <article key={action.clinic_id} className="priority-card">
            <div className="priority-head">
              <span className={`risk-icon risk-${action.status}`}>
                <AlertTriangle size={16} />
              </span>
              <button className="link-button" type="button" onClick={() => onOpen(action.clinic_id)}>
                {action.clinic}
              </button>
              <span className={`risk-pill risk-${action.status}`}>{action.status}</span>
            </div>
            <p>{action.recommendation}</p>
            {!enRoute && best && best.recommended_transfer_quantity > 0 && (
              <button
                className="primary-button"
                type="button"
                disabled={busyClinicId !== null}
                onClick={() => onApprove(action)}
              >
                <Truck size={15} />
                {busyClinicId === action.clinic_id
                  ? "Dispatching…"
                  : `Dispatch ${best.recommended_transfer_quantity} kits · ${best.delivery_time_minutes} min`}
              </button>
            )}
          </article>
        );
      })}
    </div>
  );
}
