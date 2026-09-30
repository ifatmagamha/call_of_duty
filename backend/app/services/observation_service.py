from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.schemas import (
    Observation,
    ObservationCandidate,
    validate_observation_candidate,
)
from app.services.risk_service import compute_clinic_metrics, utc_now_iso


MUTATION_FIELDS = {
    "QUEUE_COUNT_UPDATED": "people_waiting",
    "TEST_KITS_UPDATED": "test_kits_available",
    "NURSES_AVAILABLE_UPDATED": "nurses_available",
}

FIELD_EVENTS = {field: event_type for event_type, field in MUTATION_FIELDS.items()}

# Unauthenticated free text and sampled video frames never mutate numbers unreviewed.
REVIEW_ONLY_SOURCES = {"text", "video"}

def event_mutation(event: ObservationCandidate) -> tuple[str, int] | None:
    field = MUTATION_FIELDS.get(event.event_type)
    if field is None:
        if event.event_type == "CLINIC_STATUS_REPORTED":
            return None
        raise ValueError(f"Unsupported observation event: {event.event_type}")
    return field, getattr(event, field)


def updated_clinic_properties(
    clinic: dict[str, Any], event: ObservationCandidate
) -> dict[str, Any]:
    mutation = event_mutation(event)
    if mutation is None:
        return {}
    field, value = mutation
    raw = {**clinic, field: value}
    return {
        field: value,
        **compute_clinic_metrics(raw),
        "last_updated_at": utc_now_iso(),
    }


def direct_event(
    clinic_id: str,
    field: str,
    value: int,
    *,
    source_type: str,
    model_id: str,
    evidence_summary: str,
    confidence: float = 1.0,
) -> ObservationCandidate:
    """Event for sources that report a number directly (operators, edge cameras)."""
    return validate_observation_candidate(
        {
            "event_type": FIELD_EVENTS[field],
            "clinic_id": clinic_id,
            "source_type": source_type,
            "confidence": confidence,
            "observed_at": datetime.now(timezone.utc),
            "evidence_summary": evidence_summary,
            "model_id": model_id,
            field: value,
        }
    )


class ObservationStore(Protocol):
    def clinic_exists(self, clinic_id: str) -> bool: ...
    def create(self, observation: Observation) -> tuple[Observation, bool]: ...
    def get(self, observation_id: str) -> Observation | None: ...
    def list(self, **filters: Any) -> list[Observation]: ...
    def apply(self, observation_id: str) -> Observation | None: ...
    def reject(self, observation_id: str) -> Observation | None: ...


class ObservationService:
    def __init__(self, store: ObservationStore, auto_apply_confidence: float = 0.90):
        self.store = store
        self.auto_apply_confidence = auto_apply_confidence

    def process(
        self,
        event: ObservationCandidate,
        *,
        observation_id: str | None = None,
        token_usage: dict[str, int] | None = None,
    ) -> Observation:
        if not self.store.clinic_exists(event.clinic_id):
            raise ValueError("Clinic not found")
        observation = Observation(
            id=observation_id or str(uuid4()),
            event=event,
            status="pending_review",
            created_at=datetime.now(timezone.utc),
            model_id=event.model_id,
            request_id=event.request_id,
            token_usage=token_usage,
        )
        persisted, created = self.store.create(observation)
        if not created:
            return persisted
        needs_review = (
            event.source_type in REVIEW_ONLY_SOURCES
            and event.event_type in MUTATION_FIELDS
        )
        if not needs_review and event.confidence >= self.auto_apply_confidence:
            applied = self.store.apply(observation.id)
            if applied is None:
                raise ValueError("Observation not found")
            return applied
        return persisted

    def apply(self, observation_id: str) -> Observation:
        observation = self.store.apply(observation_id)
        if observation is None:
            raise ValueError("Observation not found")
        return observation

    def reject(self, observation_id: str) -> Observation:
        observation = self.store.reject(observation_id)
        if observation is None:
            raise ValueError("Observation not found")
        return observation
