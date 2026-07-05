from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.schemas import Observation, ObservationCandidate
from app.services.risk_service import compute_clinic_metrics, utc_now_iso


MUTATION_FIELDS = {
    "QUEUE_COUNT_UPDATED": "people_waiting",
    "TEST_KITS_UPDATED": "test_kits_available",
    "NURSES_AVAILABLE_UPDATED": "nurses_available",
}

UPDATE_QUERIES = {
    "QUEUE_COUNT_UPDATED": """
        MATCH (o:Observation {id: $observation_id})-[:OBSERVED_AT]->(c:Clinic)
        SET c.people_waiting = $new_value, c += $metrics,
            o.status = 'applied', o.previous_value = $previous_value,
            o.new_value = $new_value, o.reviewed_at = $reviewed_at,
            o.previous_risk_level = $previous_risk_level,
            o.new_risk_level = $new_risk_level, o.error_detail = null
        RETURN o, c
    """,
    "TEST_KITS_UPDATED": """
        MATCH (o:Observation {id: $observation_id})-[:OBSERVED_AT]->(c:Clinic)
        SET c.test_kits_available = $new_value, c += $metrics,
            o.status = 'applied', o.previous_value = $previous_value,
            o.new_value = $new_value, o.reviewed_at = $reviewed_at,
            o.previous_risk_level = $previous_risk_level,
            o.new_risk_level = $new_risk_level, o.error_detail = null
        RETURN o, c
    """,
    "NURSES_AVAILABLE_UPDATED": """
        MATCH (o:Observation {id: $observation_id})-[:OBSERVED_AT]->(c:Clinic)
        SET c.nurses_available = $new_value, c += $metrics,
            o.status = 'applied', o.previous_value = $previous_value,
            o.new_value = $new_value, o.reviewed_at = $reviewed_at,
            o.previous_risk_level = $previous_risk_level,
            o.new_risk_level = $new_risk_level, o.error_detail = null
        RETURN o, c
    """,
}


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
        if event.confidence >= self.auto_apply_confidence:
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
