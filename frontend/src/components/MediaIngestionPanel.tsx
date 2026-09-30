import { useEffect, useRef, useState } from "react";
import { Camera, FileText, Image, Mic, Square, Video } from "lucide-react";
import { describeEvent } from "../format";
import { ApiError, api } from "../api/client";
import type { Clinic, Observation, TextChannel } from "../types";

type Props = { clinics: Clinic[]; onApplied: () => Promise<void> };
type Mode = "text" | "image" | "audio" | "video" | "camera";

const MODES: { id: Mode; label: string; Icon: typeof FileText }[] = [
  { id: "text", label: "Text / SMS", Icon: FileText },
  { id: "image", label: "Photo", Icon: Image },
  { id: "audio", label: "Voice", Icon: Mic },
  { id: "video", label: "Video", Icon: Video },
  { id: "camera", label: "Live camera", Icon: Camera },
];

// MediaRecorder produces webm/ogg in most browsers; the audio model accepts WAV/MP3.
async function toWav(blob: Blob): Promise<File> {
  const context = new AudioContext();
  const buffer = await context.decodeAudioData(await blob.arrayBuffer());
  await context.close();
  const samples = buffer.getChannelData(0);
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const text = (offset: number, value: string) =>
    [...value].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, buffer.sampleRate, true);
  view.setUint32(28, buffer.sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) =>
    view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, sample)) * 0x7fff, true),
  );
  return new File([view], "voice-report.wav", { type: "audio/wav" });
}

export function MediaIngestionPanel({ clinics, onApplied }: Props) {
  const [mode, setMode] = useState<Mode>("text");
  const [clinicHint, setClinicHint] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [channel, setChannel] = useState<TextChannel>("sms");
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<Observation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [intervalSeconds, setIntervalSeconds] = useState(60);
  const recorder = useRef<MediaRecorder | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (!file || !/^(image|video|audio)\//.test(file.type)) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), []);

  function switchMode(next: Mode) {
    if (cameraOn) stopCamera();
    setMode(next); setFile(null); setResult(null); setError(null);
  }

  async function submit(run: () => Promise<{ observation: Observation }>) {
    setLoading(true); setError(null); setResult(null);
    try {
      const response = await run();
      setResult(response.observation);
      await onApplied();
    } catch (err) {
      if (err instanceof ApiError && err.status === 503 && err.message.includes("Crusoe inference")) {
        setError("AI extraction needs CRUSOE_API_KEY in .env. Camera counts and manual updates work without it.");
      } else {
        setError(err instanceof Error ? err.message : "Ingestion failed.");
      }
    } finally { setLoading(false); }
  }

  function upload() {
    const hint = clinicHint || undefined;
    if (mode === "text") return submit(() => api.ingestText(text, channel, hint));
    if (!file) return;
    if (mode === "image") return submit(() => api.ingestImage(file, hint));
    if (mode === "audio") return submit(() => api.ingestAudio(file, hint));
    if (mode === "video") return submit(() => api.ingestVideo(file, hint));
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
    next.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      try { setFile(await toWav(new Blob(chunks, { type: next.mimeType }))); }
      catch { setError("Could not convert the recording; upload a WAV or MP3 file instead."); }
    };
    recorder.current = next; next.start(); setRecording(true);
  }

  function stopRecording() { recorder.current?.stop(); setRecording(false); }

  async function startCamera() {
    setError(null);
    if (!clinicHint) { setError("Choose the clinic this camera watches."); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      setCameraOn(true);
    } catch { setError("Camera access was denied or no camera is available."); }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraOn(false);
  }

  useEffect(() => {
    if (!cameraOn) return;
    const capture = () => {
      const video = videoRef.current;
      if (!video || !video.videoWidth) return;
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      canvas.getContext("2d")?.drawImage(video, 0, 0);
      canvas.toBlob((blob) => {
        if (!blob) return;
        const frame = new File([blob], "camera-frame.jpg", { type: "image/jpeg" });
        void submit(() => api.ingestImage(frame, clinicHint));
      }, "image/jpeg", 0.85);
    };
    const first = window.setTimeout(capture, 1500);
    const timer = window.setInterval(capture, intervalSeconds * 1000);
    return () => { window.clearTimeout(first); window.clearInterval(timer); };
  }, [cameraOn, intervalSeconds, clinicHint]);

  const accept = { image: "image/jpeg,image/png", audio: "audio/wav,audio/mpeg,.wav,.mp3", video: "video/mp4" };

  return (
    <section className="panel-section">
      <div><p className="eyebrow">Multimodal intake</p><h2 className="panel-title">Report what is happening</h2></div>
      <div className="mode-tabs" role="tablist">
        {MODES.map(({ id, label, Icon }) => (
          <button key={id} role="tab" aria-selected={mode === id} type="button"
            className={mode === id ? "mode-tab active" : "mode-tab"} onClick={() => switchMode(id)}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>
      <label className="field-label">{mode === "camera" ? "Clinic this camera watches" : "Clinic (optional hint)"}
        <select className="number-input" value={clinicHint} onChange={(e) => setClinicHint(e.target.value)}>
          <option value="">{mode === "camera" ? "Choose a clinic" : "Let the evidence identify it"}</option>
          {clinics.map((clinic) => <option key={clinic.id} value={clinic.id}>{clinic.name}</option>)}
        </select>
      </label>

      {mode === "text" && <>
        <label className="field-label">Channel
          <select className="number-input" value={channel} onChange={(e) => setChannel(e.target.value as TextChannel)}>
            <option value="sms">SMS / WhatsApp</option>
            <option value="phone_transcript">Phone call transcript</option>
            <option value="field_report">Field report</option>
            <option value="other">Other</option>
          </select>
        </label>
        <textarea className="text-input" rows={4} maxLength={4000} value={text}
          placeholder="e.g. Lingwala: only 12 test kits left, 3 suspected cases this morning"
          onChange={(e) => setText(e.target.value)} />
        <button className="primary-button" disabled={!text.trim() || loading} onClick={upload}>Extract fact</button>
        <p className="panel-note">Numbers from text always wait for human review.</p>
      </>}

      {(mode === "image" || mode === "audio" || mode === "video") && <>
        <input type="file" accept={accept[mode]} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {mode === "audio" && (
          <button className="secondary-button" type="button" onClick={recording ? stopRecording : startRecording}>
            {recording ? <Square size={15} /> : <Mic size={15} />}{recording ? "Stop recording" : "Record voice report"}
          </button>
        )}
        {preview && mode === "image" && <img className="media-preview" src={preview} alt="Selected evidence" />}
        {preview && mode === "audio" && <audio controls src={preview} className="w-full" />}
        {preview && mode === "video" && <video controls src={preview} className="media-preview" />}
        <button className="primary-button" disabled={!file || loading} onClick={upload}>
          {loading ? "Extracting…" : `Upload ${mode}`}
        </button>
        {mode === "video" && <p className="panel-note">MP4 up to 30 s. Six frames are sampled; counts always wait for review.</p>}
        {mode === "audio" && <p className="panel-note">Recorded phone calls can be uploaded here as WAV/MP3.</p>}
      </>}

      {mode === "camera" && <>
        <video ref={videoRef} className="media-preview camera-feed" muted playsInline hidden={!cameraOn} />
        <label className="field-label">Send a frame every
          <select className="number-input" value={intervalSeconds} onChange={(e) => setIntervalSeconds(Number(e.target.value))}>
            {[15, 30, 60, 300].map((s) => <option key={s} value={s}>{s < 60 ? `${s} s` : `${s / 60} min`}</option>)}
          </select>
        </label>
        <button className={cameraOn ? "secondary-button" : "primary-button"} type="button"
          onClick={cameraOn ? stopCamera : startCamera}>
          {cameraOn ? <><Square size={15} /> Stop camera</> : <><Camera size={15} /> Connect this device's camera</>}
        </button>
        <p className="panel-note">
          Each frame is counted by the vision model. Edge counters can instead POST counts to
          <code> /ingestion/camera</code> (see <code>scripts/simulate_cameras.py</code>).
        </p>
      </>}

      {error && <div className="panel-error">{error}</div>}
      {result && <article className="observation-card"><strong>{describeEvent(result.event)}</strong>
        <span>{result.event.clinic_id} · {Math.round(result.event.confidence * 100)}% confidence · {result.status.replace("_", " ")}</span>
        <p>{result.event.transcript ?? result.event.evidence_summary}</p></article>}
    </section>
  );
}
