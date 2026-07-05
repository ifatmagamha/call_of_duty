import { useEffect, useState } from "react";
import { Play, Square } from "lucide-react";
import { api } from "../api/client";
import type { SituationBriefing } from "../types";

export function SituationBriefingPanel() {
  const [briefing, setBriefing] = useState<SituationBriefing | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  async function generate() {
    setLoading(true); setError(null); window.speechSynthesis?.cancel();
    try { setBriefing(await api.generateBriefing()); }
    catch (err) { setError(err instanceof Error ? err.message : "Briefing generation failed."); }
    finally { setLoading(false); }
  }
  function read() {
    if (!briefing || !window.speechSynthesis) return;
    const messages = briefing.center_messages.map((item) => `${item.clinic_id}: ${item.message}`).join(". ");
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(`${briefing.headline}. ${briefing.summary}. ${messages}`));
  }

  return <section className="panel-section">
    <div><p className="eyebrow">Kimi global synthesis</p><h2 className="panel-title">Situation briefing</h2></div>
    <button className="primary-button" disabled={loading} onClick={generate}>{loading ? "Generating…" : "Generate briefing"}</button>
    <p className="panel-note">Read aloud uses local browser speech synthesis, not a Crusoe audio model.</p>
    {error && <div className="panel-error">{error}</div>}
    {briefing && <article className="briefing-card">
      <span className={`risk-pill risk-${briefing.global_status === "degrading" ? "high" : briefing.global_status === "watch" ? "medium" : briefing.global_status}`}>{briefing.global_status}</span>
      <h3>{briefing.headline}</h3><p>{briefing.summary}</p>
      <ul className="reason-list">{briefing.detected_trends.map((trend) => <li key={trend}>{trend}</li>)}</ul>
      {briefing.center_messages.map((item) => <p key={item.clinic_id}><strong>{item.clinic_id}:</strong> {item.message}</p>)}
      <div className="button-row"><button className="secondary-button" onClick={read}><Play size={15}/> Read aloud</button><button className="secondary-button" onClick={() => window.speechSynthesis?.cancel()}><Square size={15}/> Stop</button></div>
    </article>}
  </section>;
}
