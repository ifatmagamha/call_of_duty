import type { ObservationEvent } from "./types";

export function formatHours(value: number | null) {
  return value === null ? "n/a" : `${value.toFixed(2)} h`;
}

export function describeEvent(event: ObservationEvent) {
  if (event.event_type === "QUEUE_COUNT_UPDATED") return `${event.people_waiting} people waiting`;
  if (event.event_type === "TEST_KITS_UPDATED") return `${event.test_kits_available} test kits`;
  if (event.event_type === "NURSES_AVAILABLE_UPDATED") return `${event.nurses_available} nurses`;
  return event.status_note;
}
