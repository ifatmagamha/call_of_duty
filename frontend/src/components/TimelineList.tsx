import { Camera, FileText, Image, Mic, Pencil, Truck, Video } from "lucide-react";
import type { TimelineEntry } from "../types";

const SOURCE_ICON = {
  camera: Camera,
  image: Image,
  audio: Mic,
  video: Video,
  text: FileText,
  manual: Pencil,
} as const;

function timeAgo(iso: string) {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

type Props = {
  entries: TimelineEntry[];
  showClinic?: boolean;
  onSelectClinic?: (clinicId: string) => void;
};

export function TimelineList({ entries, showClinic = false, onSelectClinic }: Props) {
  if (entries.length === 0) {
    return <p className="panel-muted">No activity recorded yet.</p>;
  }
  return (
    <ol className="timeline">
      {entries.map((entry) => {
        const Icon =
          entry.kind === "transfer"
            ? Truck
            : SOURCE_ICON[entry.source_type as keyof typeof SOURCE_ICON] ?? FileText;
        return (
          <li key={entry.id} className={`timeline-item status-${entry.status}`}>
            <span className="timeline-icon"><Icon size={14} /></span>
            <div className="timeline-body">
              <div className="timeline-head">
                <strong>{entry.title}</strong>
                <time dateTime={entry.at} title={new Date(entry.at).toLocaleString()}>
                  {timeAgo(entry.at)}
                </time>
              </div>
              {showClinic && (
                <button
                  className="link-button"
                  type="button"
                  onClick={() => onSelectClinic?.(entry.clinic_id)}
                >
                  {entry.clinic_name}
                </button>
              )}
              <p>
                {entry.detail}
                {entry.status !== "applied" && entry.kind === "observation" && (
                  <span className="timeline-status"> · {entry.status.replace("_", " ")}</span>
                )}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function Sparkline({ entries, field }: { entries: TimelineEntry[]; field: string }) {
  const points = entries
    .filter((entry) => entry.field === field && entry.value !== null)
    .reverse();
  if (points.length < 2) {
    return <p className="panel-note">Trend appears after two or more updates.</p>;
  }
  const values = points.map((point) => point.value as number);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const path = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 36 - ((value - min) / span) * 32;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <figure className="sparkline">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img"
        aria-label={`Trend from ${values[0]} to ${values[values.length - 1]}`}>
        <path d={path} fill="none" stroke="currentColor" strokeWidth="1.6"
          vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption>
        <span>{values[0]}</span>
        <span>min {min} · max {max}</span>
        <strong>{values[values.length - 1]}</strong>
      </figcaption>
    </figure>
  );
}
