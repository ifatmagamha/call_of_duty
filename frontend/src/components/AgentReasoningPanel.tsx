import { AlertTriangle, Route } from "lucide-react";
import type { AgentRecommendation, ResupplyOption, Transfer } from "../types";

type AgentReasoningPanelProps = {
  recommendation: AgentRecommendation | null;
  transfers: Transfer[];
  loading: boolean;
  validatingSourceId: string | null;
  actionMessage: string | null;
  onValidateTransfer: (option: ResupplyOption) => Promise<void>;
  onRejectTransfer: () => void;
};

export function AgentReasoningPanel({
  recommendation,
  transfers,
  loading,
  validatingSourceId,
  actionMessage,
  onValidateTransfer,
  onRejectTransfer,
}: AgentReasoningPanelProps) {
  if (loading) {
    return <div className="panel-muted">Loading recommendation...</div>;
  }

  if (!recommendation) {
    return <div className="panel-muted">Clinic recommendations appear here.</div>;
  }

  const proposals = recommendation.options
    .filter((option) => option.recommended_transfer_quantity > 0)
    .slice(0, 3);
  const ongoingForClinic = transfers.some(
    (transfer) => transfer.target_clinic_id === recommendation.clinic_id,
  );

  function TransferAction({ option }: { option: ResupplyOption }) {
    const disabled =
      option.source_type !== "warehouse" ||
      option.recommended_transfer_quantity <= 0 ||
      ongoingForClinic ||
      validatingSourceId !== null;

    return (
      <button
        className="primary-button transfer-button"
        disabled={disabled}
        onClick={() => onValidateTransfer(option)}
        type="button"
      >
        {validatingSourceId === option.source_id
          ? "Validating"
          : `Validate option ${option.rank}`}
      </button>
    );
  }

  return (
    <section className="panel-section">
      <div className="flex items-start gap-3">
        <span className={`risk-icon risk-${recommendation.status}`}>
          <AlertTriangle size={18} />
        </span>
        <div>
          <p className="eyebrow">Agent reasoning</p>
          <h2 className="panel-title">{recommendation.recommendation}</h2>
        </div>
      </div>

      <div className="agent-source">Deterministic backend explanation</div>

      <ul className="reason-list">
        {recommendation.reasoning.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>

      {actionMessage && (
        <article className="action-card">
          <p className="eyebrow">Agent action</p>
          <p>{actionMessage}</p>
        </article>
      )}

      {proposals.length > 0 && recommendation.status !== "normal" && (
        <div className="space-y-2">
          <p className="eyebrow">Proposals</p>
          {ongoingForClinic && (
            <div className="panel-note">
              A transfer is already ongoing for this clinic, so new validations are paused.
            </div>
          )}
          {proposals.map((option) => (
            <article className="proposal-card" key={option.source_id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3>Option {option.rank}: {option.source_name}</h3>
                  <p>
                    {option.source_type} • {option.road_status} route •{" "}
                    {option.delivery_time_minutes} min
                  </p>
                </div>
                <span className="rank-badge">#{option.rank}</span>
              </div>
              <div className="option-footer">
                <span>
                  <Route size={14} /> {option.recommended_transfer_quantity} kits
                </span>
                <span>{option.reason}</span>
              </div>
              <TransferAction option={option} />
            </article>
          ))}
          <article className="proposal-card none-card">
            <div>
              <h3>None</h3>
              <p>No transfer is launched. Warehouse stock stays unchanged.</p>
            </div>
            <ul className="reason-list compact-reasons">
              <li>Choose this if the proposed routes should wait for human review.</li>
              <li>The system will keep the deterministic recommendation visible.</li>
            </ul>
            <button
              className="secondary-button transfer-button"
              disabled={validatingSourceId !== null}
              onClick={onRejectTransfer}
              type="button"
            >
              Choose none
            </button>
          </article>
        </div>
      )}

    </section>
  );
}
