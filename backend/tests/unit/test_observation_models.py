from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.observations import validate_observation_candidate


BASE = {
    "clinic_id": "clinic-b",
    "source_type": "image",
    "confidence": 0.95,
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "evidence_summary": "Visible operational board.",
    "model_id": "google/gemma-4-31b-it",
}


@pytest.mark.parametrize(
    ("event_type", "field", "value"),
    [
        ("QUEUE_COUNT_UPDATED", "people_waiting", 14),
        ("TEST_KITS_UPDATED", "test_kits_available", 20),
        ("NURSES_AVAILABLE_UPDATED", "nurses_available", 3),
        ("CLINIC_STATUS_REPORTED", "status_note", "Generator is unstable."),
    ],
)
def test_each_observation_variant_is_typed(event_type, field, value):
    event = validate_observation_candidate(
        {**BASE, "event_type": event_type, field: value}
    )

    assert event.event_type == event_type
    assert getattr(event, field) == value


@pytest.mark.parametrize(
    ("event_type", "field"),
    [
        ("QUEUE_COUNT_UPDATED", "people_waiting"),
        ("TEST_KITS_UPDATED", "test_kits_available"),
        ("NURSES_AVAILABLE_UPDATED", "nurses_available"),
    ],
)
def test_negative_operational_values_are_rejected(event_type, field):
    with pytest.raises(ValidationError):
        validate_observation_candidate(
            {**BASE, "event_type": event_type, field: -1}
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_invalid_confidence_is_rejected(confidence):
    with pytest.raises(ValidationError):
        validate_observation_candidate(
            {
                **BASE,
                "event_type": "QUEUE_COUNT_UPDATED",
                "people_waiting": 1,
                "confidence": confidence,
            }
        )


def test_unknown_event_type_is_rejected():
    with pytest.raises(ValidationError):
        validate_observation_candidate(
            {**BASE, "event_type": "TRANSFER_APPROVED", "quantity": 10}
        )


def test_status_note_must_not_be_blank():
    with pytest.raises(ValidationError):
        validate_observation_candidate(
            {**BASE, "event_type": "CLINIC_STATUS_REPORTED", "status_note": "  "}
        )
