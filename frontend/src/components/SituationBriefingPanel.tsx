import { type FormEvent, useEffect, useState } from "react";
import { MessageSquare, Play, Square } from "lucide-react";
import { api } from "../api/client";
import type { SituationAnswer, SituationBriefing } from "../types";

export function SituationBriefingPanel() {
  const [briefing, setBriefing] = useState<SituationBriefing | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<SituationAnswer | null>(null);
  const [asking, setAsking] = useState(false);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  async function ask(event: FormEvent) {
    event.preventDefault();
    setAsking(true); setError(null);
    try { setAnswer(await api.ask(question)); }
    catch (err) { setError(err instanceof Error ? err.message : "Question failed."); }
    finally { setAsking(false); }
  }

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
    <div><p className="eyebrow">Ask the situation</p><h2 className="panel-title">Natural-language answers</h2></div>
    <form className="ask-form" onSubmit={ask}>
      <input className="number-input" value={question} minLength={3} maxLength={500} required
        placeholder="Which clinics run out of kits first?" onChange={(e) => setQuestion(e.target.value)} />
      <button className="primary-button" disabled={asking || question.trim().length < 3}>
        <MessageSquare size={15} />{asking ? "Thinking…" : "Ask"}
      </button>
    </form>
    {answer && <article className="briefing-card">
      <p>{answer.answer}</p>
      {answer.suggested_actions.length > 0 && <ul className="reason-list">{answer.suggested_actions.map((a) => <li key={a}>{a}</li>)}</ul>}
      <span className="panel-note">Grounded in live graph data · {answer.model_id}</span>
    </article>}
    <div><p className="eyebrow">Global synthesis</p><h2 className="panel-title">Situation briefing</h2></div>
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
