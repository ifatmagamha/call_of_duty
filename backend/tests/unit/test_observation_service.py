from datetime import datetime, timezone

import pytest

from app.schemas import Observation, validate_observation_candidate
from app.services.observation_service import (
    ObservationService,
    event_mutation,
    updated_clinic_properties,
)


NOW = datetime.now(timezone.utc)


def candidate(event_type="QUEUE_COUNT_UPDATED", confidence=0.95, **fields):
    values = {
        "event_type": event_type,
        "clinic_id": "clinic-b",
        "source_type": "manual",
        "confidence": confidence,
        "observed_at": NOW.isoformat(),
        "evidence_summary": "Operator supplied fixture.",
        "model_id": "fixture",
    }
    defaults = {
        "QUEUE_COUNT_UPDATED": {"people_waiting": 120},
        "TEST_KITS_UPDATED": {"test_kits_available": 20},
        "NURSES_AVAILABLE_UPDATED": {"nurses_available": 1},
        "CLINIC_STATUS_REPORTED": {"status_note": "Generator unstable."},
    }
    return validate_observation_candidate(values | defaults[event_type] | fields)


class MemoryStore:
    def __init__(self, clinic_exists=True):
        self.clinic_exists_value = clinic_exists
        self.items = {}
        self.applied = []
        self.rejected = []

    def clinic_exists(self, clinic_id):
        return self.clinic_exists_value

    def create(self, observation):
        existing = self.items.get(observation.id)
        if existing:
            return existing, False
        self.items[observation.id] = observation
        return observation, True

    def get(self, observation_id):
        return self.items.get(observation_id)

    def list(self, **filters):
        return list(self.items.values())

    def apply(self, observation_id):
        item = self.items[observation_id]
        if item.status == "applied":
            return item
        mutation = event_mutation(item.event)
        previous = 10 if mutation else None
        new = mutation[1] if mutation else None
        applied = item.model_copy(
            update={
                "status": "applied",
                "previous_value": previous,
                "new_value": new,
                "reviewed_at": NOW,
            }
        )
        self.items[observation_id] = applied
        self.applied.append(observation_id)
        return applied

    def reject(self, observation_id):
        item = self.items[observation_id]
        rejected = item.model_copy(update={"status": "rejected", "reviewed_at": NOW})
        self.items[observation_id] = rejected
        self.rejected.append(observation_id)
        return rejected


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("QUEUE_COUNT_UPDATED", ("people_waiting", 120)),
        ("TEST_KITS_UPDATED", ("test_kits_available", 20)),
        ("NURSES_AVAILABLE_UPDATED", ("nurses_available", 1)),
        ("CLINIC_STATUS_REPORTED", None),
    ],
)
def test_event_to_property_allowlist(event_type, expected):
    assert event_mutation(candidate(event_type)) == expected


def test_unknown_clinic_is_rejected_before_persistence():
    store = MemoryStore(clinic_exists=False)
    with pytest.raises(ValueError, match="Clinic not found"):
        ObservationService(store).process(candidate())
    assert store.items == {}


def test_confidence_threshold_auto_applies_and_low_confidence_waits():
    store = MemoryStore()
    high = ObservationService(store, auto_apply_confidence=0.90).process(
        candidate(confidence=0.90), observation_id="high"
    )
    low = ObservationService(store, auto_apply_confidence=0.90).process(
        candidate(confidence=0.89), observation_id="low"
    )
    assert high.status == "applied"
    assert low.status == "pending_review"
    assert store.applied == ["high"]


def test_apply_and_reject_pending_observations():
    store = MemoryStore()
    service = ObservationService(store)
    service.process(candidate(confidence=0.5), observation_id="apply-me")
    service.process(candidate(confidence=0.5), observation_id="reject-me")
    assert service.apply("apply-me").status == "applied"
    assert service.reject("reject-me").status == "rejected"


def test_applying_same_observation_id_is_idempotent():
    store = MemoryStore()
    service = ObservationService(store)
    first = service.process(candidate(), observation_id="same")
    second = service.process(candidate(), observation_id="same")
    assert first.id == second.id
    assert store.applied == ["same"]


def test_numeric_apply_recomputes_deterministic_metrics():
    clinic = {
        "test_kits_available": 35,
        "people_waiting": 96,
        "nurses_available": 2,
        "threshold_min_kits": 50,
    }
    props = updated_clinic_properties(clinic, candidate("TEST_KITS_UPDATED"))
    assert props["test_kits_available"] == 20
    assert props["testing_capacity_per_hour"] == 24
    assert props["operations_remaining_hours"] == 0.83
    assert props["risk_level"] == "critical"


def test_status_report_does_not_change_numeric_state():
    clinic = {
        "test_kits_available": 35,
        "people_waiting": 96,
        "nurses_available": 2,
        "threshold_min_kits": 50,
    }
    assert updated_clinic_properties(clinic, candidate("CLINIC_STATUS_REPORTED")) == {}
