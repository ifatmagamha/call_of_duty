"""
Speech Transcription Agent
===========================

Turns audio - live calls or recordings - into a structured, high-accuracy
transcript, meant to be consumed by other agents in a pipeline (alerting,
dashboards, task routing, coordination tools for crisis/response teams).

Pipeline:
  audio -> VAD segmentation -> Whisper transcription -> (optional) speaker
  diarization -> keyword flagging -> structured JSON output -> (optional) webhook push

Requirements:
    pip install faster-whisper sounddevice numpy webrtcvad soundfile requests
    # optional, for speaker diarization:
    pip install pyannote.audio

Usage:
    # Transcribe a recorded file
    python speech_agent.py --source call_recording.wav --output transcript.json

    # Transcribe live from microphone / call audio input device
    python speech_agent.py --source mic --output live_transcript.json

    # With speaker diarization and keyword flagging, pushed to a downstream agent
    python speech_agent.py --source call.wav --diarize \\
        --keywords "outbreak,evacuate,casualties,urgent" \\
        --webhook http://localhost:8000/ingest

Output JSON schema (see SCHEMA below) is stable and meant to be relied on
by other agents - do not rename fields without updating consumers.
"""

import argparse
import json
import os
import queue
import time
import uuid
from datetime import datetime, timezone

import numpy as np

# --------------------------------------------------------------------------
# Output schema (documented so downstream agents have a stable contract)
# --------------------------------------------------------------------------
# {
#   "session_id": "uuid",
#   "source_type": "file" | "live_mic" | "live_call",
#   "source_name": "call_recording.wav",
#   "started_at": "2026-07-05T14:32:10Z",
#   "language": "en",
#   "full_text": "...",
#   "segments": [
#     {
#       "id": 0,
#       "start": 0.0,
#       "end": 4.2,
#       "speaker": "SPEAKER_00" | "unknown",
#       "text": "...",
#       "confidence": 0.93,
#       "flags": ["urgent"]
#     },
#     ...
#   ],
#   "flag_summary": {"urgent": 3, "outbreak": 1}
# }


def build_payload(session_id, source_type, source_name, language, segments):
    flag_summary = {}
    for seg in segments:
        for flag in seg.get("flags", []):
            flag_summary[flag] = flag_summary.get(flag, 0) + 1

    return {
        "session_id": session_id,
        "source_type": source_type,
        "source_name": source_name,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "language": language,
        "full_text": " ".join(seg["text"].strip() for seg in segments).strip(),
        "segments": segments,
        "flag_summary": flag_summary,
    }


def flag_keywords(text, keywords):
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


# --------------------------------------------------------------------------
# Transcription core (faster-whisper)
# --------------------------------------------------------------------------
def load_whisper_model(model_size="large-v3", device="auto", compute_type="auto"):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_audio_array(model, audio, sample_rate, language=None):
    """Run Whisper on a numpy float32 audio array, return list of segment dicts."""
    segments_out = []
    segments, info = model.transcribe(
        audio,
        language=language,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
    )
    for i, seg in enumerate(segments):
        avg_logprob = getattr(seg, "avg_logprob", None)
        confidence = round(float(np.exp(avg_logprob)), 3) if avg_logprob is not None else None
        segments_out.append({
            "id": i,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "speaker": "unknown",
            "text": seg.text.strip(),
            "confidence": confidence,
            "flags": [],
        })
    return segments_out, info.language


def transcribe_file(model, path, language=None):
    segments, detected_language = transcribe_audio_array(model, path, sample_rate=None, language=language)
    return segments, detected_language


# --------------------------------------------------------------------------
# Speaker diarization (optional)
# --------------------------------------------------------------------------
def apply_diarization(path, segments, hf_token=None):
    """Tag each segment with a speaker label using pyannote.audio, if available."""
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        print("pyannote.audio not installed - skipping diarization, speakers will be 'unknown'.")
        return segments

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token or os.environ.get("HF_TOKEN"),
    )
    diarization = pipeline(path)

    for seg in segments:
        mid_point = (seg["start"] + seg["end"]) / 2
        speaker_label = "unknown"
        for turn, _, label in diarization.itertracks(yield_label=True):
            if turn.start <= mid_point <= turn.end:
                speaker_label = label
                break
        seg["speaker"] = speaker_label

    return segments


# --------------------------------------------------------------------------
# Live microphone / call-audio streaming
# --------------------------------------------------------------------------
def stream_from_mic(model, language, keywords, on_segment, sample_rate=16000, chunk_seconds=0.5,
                     silence_seconds_to_cut=0.8, energy_threshold=0.01):
    """
    Capture live audio, cut into speech segments on pauses (simple energy-based VAD),
    transcribe each finished segment, and call on_segment(segment_dict) as it's ready.

    This is intentionally simple (energy-based) to avoid a hard webrtcvad/torch
    dependency here; swap in webrtcvad or silero-vad for noisier environments.
    """
    import sounddevice as sd

    audio_q = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        audio_q.put(indata.copy())

    buffer = np.zeros((0,), dtype=np.float32)
    silence_chunks = 0
    max_silence_chunks = int(silence_seconds_to_cut / chunk_seconds)
    seg_id = 0

    print("Listening... (Ctrl+C to stop)")
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32",
                         blocksize=int(sample_rate * chunk_seconds), callback=audio_callback):
        try:
            while True:
                chunk = audio_q.get()
                chunk = chunk.flatten()
                energy = np.sqrt(np.mean(chunk ** 2))
                buffer = np.concatenate([buffer, chunk])

                if energy < energy_threshold:
                    silence_chunks += 1
                else:
                    silence_chunks = 0

                long_enough = len(buffer) / sample_rate >= 1.0
                if silence_chunks >= max_silence_chunks and long_enough:
                    segments, detected_lang = transcribe_audio_array(model, buffer, sample_rate, language)
                    for seg in segments:
                        seg["id"] = seg_id
                        seg["flags"] = flag_keywords(seg["text"], keywords)
                        on_segment(seg)
                        seg_id += 1
                    buffer = np.zeros((0,), dtype=np.float32)
                    silence_chunks = 0
        except KeyboardInterrupt:
            print("\nStopped listening.")


# --------------------------------------------------------------------------
# Output delivery
# --------------------------------------------------------------------------
def write_output(payload, output_path):
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Transcript written to {output_path}")


def push_to_webhook(payload, webhook_url):
    import requests
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        print(f"Pushed transcript to {webhook_url} (status {resp.status_code})")
    except Exception as e:
        print(f"Failed to push to webhook {webhook_url}: {e}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Speech Transcription Agent")
    parser.add_argument("--source", required=True,
                         help="Path to an audio file, or 'mic' for live capture")
    parser.add_argument("--output", default="transcript.json", help="Output JSON path")
    parser.add_argument("--model", default="large-v3",
                         help="faster-whisper model size (tiny/base/small/medium/large-v3)")
    parser.add_argument("--language", default=None, help="Force language code (e.g. 'en'); default = auto-detect")
    parser.add_argument("--diarize", action="store_true", help="Tag segments with speaker labels")
    parser.add_argument("--hf-token", default=None, help="HuggingFace token for pyannote diarization model")
    parser.add_argument("--keywords", default="",
                         help="Comma-separated keywords to flag in segments, e.g. 'outbreak,urgent,evacuate'")
    parser.add_argument("--webhook", default=None, help="POST the final transcript JSON to this URL")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    session_id = str(uuid.uuid4())
    model = load_whisper_model(args.model)

    if args.source == "mic":
        segments = []

        def on_segment(seg):
            segments.append(seg)
            print(f"[{seg['start']:.1f}-{seg['end']:.1f}s] {seg['speaker']}: {seg['text']}"
                  + (f"  FLAGS: {seg['flags']}" if seg["flags"] else ""))
            # Write incrementally so downstream agents can poll the file live
            payload = build_payload(session_id, "live_mic", "microphone", args.language, segments)
            write_output(payload, args.output)
            if args.webhook:
                push_to_webhook(payload, args.webhook)

        stream_from_mic(model, args.language, keywords, on_segment)

        payload = build_payload(session_id, "live_mic", "microphone", args.language, segments)
        write_output(payload, args.output)
        if args.webhook:
            push_to_webhook(payload, args.webhook)

    else:
        if not os.path.exists(args.source):
            raise FileNotFoundError(f"Audio file not found: {args.source}")

        segments, detected_language = transcribe_file(model, args.source, args.language)
        for seg in segments:
            seg["flags"] = flag_keywords(seg["text"], keywords)

        if args.diarize:
            segments = apply_diarization(args.source, segments, args.hf_token)

        payload = build_payload(session_id, "file", os.path.basename(args.source),
                                 args.language or detected_language, segments)
        write_output(payload, args.output)
        if args.webhook:
            push_to_webhook(payload, args.webhook)


if __name__ == "__main__":
    main()