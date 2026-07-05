import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Observation } from "../types";

type Props = { refreshKey: number; onApplied: () => Promise<void> };

function value(event: Observation["event"]) {
  if (event.event_type === "QUEUE_COUNT_UPDATED") return `Queue: ${event.people_waiting}`;
  if (event.event_type === "TEST_KITS_UPDATED") return `Kits: ${event.test_kits_available}`;
  if (event.event_type === "NURSES_AVAILABLE_UPDATED") return `Nurses: ${event.nurses_available}`;
  return event.status_note;
}

export function ObservationReviewPanel({ refreshKey, onApplied }: Props) {
  const [items, setItems] = useState<Observation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.getObservations({ status: "pending_review" }).then(setItems).catch((e) => setError(e.message)), []);
  useEffect(() => { void load(); }, [load, refreshKey]);

  async function act(item: Observation, action: "apply" | "reject") {
    setError(null);
    try {
      if (action === "apply") { await api.applyObservation(item.id); await onApplied(); }
      else await api.rejectObservation(item.id);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Review action failed."); }
  }

  return (
    <section className="panel-section">
      <div><p className="eyebrow">Human review</p><h2 className="panel-title">Pending observations</h2></div>
      {error && <div className="panel-error">{error}</div>}
      {items.length === 0 && <p className="panel-muted">No observations need review.</p>}
      {items.map((item) => <article className="observation-card" key={item.id}>
        <strong>{item.event.clinic_id} · {value(item.event)}</strong>
        <span>{item.event.source_type} · {Math.round(item.event.confidence * 100)}% confidence</span>
        <p>{item.event.transcript ?? item.event.raw_text ?? item.event.evidence_summary}</p>
        <div className="button-row"><button className="primary-button" onClick={() => act(item, "apply")}>Apply</button><button className="secondary-button" onClick={() => act(item, "reject")}>Reject</button></div>
      </article>)}
    </section>
  );
}
