import { useEffect, useRef, useState } from "react";
import { Camera, Mic, Square } from "lucide-react";
import { api } from "../api/client";
import type { Clinic, Observation } from "../types";

type Props = { clinics: Clinic[]; onApplied: () => Promise<void> };

function extractedValue(observation: Observation) {
  const event = observation.event;
  if (event.event_type === "QUEUE_COUNT_UPDATED") return `${event.people_waiting} people waiting`;
  if (event.event_type === "TEST_KITS_UPDATED") return `${event.test_kits_available} test kits`;
  if (event.event_type === "NURSES_AVAILABLE_UPDATED") return `${event.nurses_available} nurses`;
  return event.status_note;
}

export function MediaIngestionPanel({ clinics, onApplied }: Props) {
  const [clinicHint, setClinicHint] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<Observation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    if (!image) return setPreview(null);
    const url = URL.createObjectURL(image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  async function upload(kind: "image" | "audio") {
    const file = kind === "image" ? image : audio;
    if (!file) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const response = kind === "image"
        ? await api.ingestImage(file, clinicHint || undefined)
        : await api.ingestAudio(file, clinicHint || undefined);
      setResult(response.observation);
      if (response.observation.status === "applied") await onApplied();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Media ingestion failed.");
    } finally { setLoading(false); }
  }

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      setError("Microphone recording is not supported here; choose a WAV or MP3 file."); return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks: BlobPart[] = [];
    const next = new MediaRecorder(stream);
    next.ondataavailable = (event) => chunks.push(event.data);
    next.onstop = () => {
      const blob = new Blob(chunks, { type: next.mimeType });
      stream.getTracks().forEach((track) => track.stop());
      if (!/audio\/(wav|mpeg|mp3)/.test(blob.type)) {
        setError(`This browser recorded ${blob.type || "an unsupported format"}. Export WAV/MP3 or use the file fallback.`);
        return;
      }
      setAudio(new File([blob], "clinic-report", { type: blob.type }));
    };
    recorder.current = next; next.start(); setRecording(true);
  }

  function stopRecording() { recorder.current?.stop(); setRecording(false); }

  return (
    <section className="panel-section">
      <div><p className="eyebrow">Crusoe observations</p><h2 className="panel-title">Image or audio report</h2></div>
      <label className="field-label">Optional clinic hint
        <select className="number-input" value={clinicHint} onChange={(e) => setClinicHint(e.target.value)}>
          <option value="">Let evidence identify it</option>
          {clinics.map((clinic) => <option key={clinic.id} value={clinic.id}>{clinic.name}</option>)}
        </select>
      </label>
      <label className="field-label"><Camera size={15} /> Image (JPEG/PNG)
        <input type="file" accept="image/jpeg,image/png" onChange={(e) => setImage(e.target.files?.[0] ?? null)} />
      </label>
      {preview && <img className="media-preview" src={preview} alt="Selected clinic evidence" />}
      <button className="primary-button" disabled={!image || loading} onClick={() => upload("image")}>Upload image</button>
      <label className="field-label">Audio fallback (WAV/MP3)
        <input type="file" accept="audio/wav,audio/mpeg,.wav,.mp3" onChange={(e) => setAudio(e.target.files?.[0] ?? null)} />
      </label>
      <div className="button-row">
        <button className="secondary-button" type="button" onClick={recording ? stopRecording : startRecording}>
          {recording ? <Square size={15} /> : <Mic size={15} />}{recording ? "Stop recording" : "Record"}
        </button>
        <button className="primary-button" disabled={!audio || loading} onClick={() => upload("audio")}>Upload audio</button>
      </div>
      {error && <div className="panel-error">{error}</div>}
      {result && <article className="observation-card"><strong>{extractedValue(result)}</strong><span>{Math.round(result.event.confidence * 100)}% confidence · {result.status}</span><p>{result.event.evidence_summary}</p></article>}
    </section>
  );
}
