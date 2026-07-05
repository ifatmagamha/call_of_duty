import pytest
from pydantic import ValidationError

from app.schemas.briefings import validate_situation_briefing


def briefing_payload(clinic_id="clinic-b"):
    return {
        "global_status": "watch",
        "headline": "Two clinics need attention",
        "summary": "Queue pressure is rising at one clinic.",
        "detected_trends": ["clinic-b queue increased from 80 to 96"],
        "center_messages": [
            {"clinic_id": clinic_id, "message": "Review the current queue."}
        ],
        "recommended_operator_checks": ["Confirm the latest clinic report."],
        "generated_at": "2026-07-05T10:00:00+00:00",
        "model_id": "moonshotai/Kimi-K2.6",
        "source_observation_ids": ["obs-1"],
    }


def test_briefing_accepts_only_known_center_references():
    briefing = validate_situation_briefing(briefing_payload(), {"clinic-b"})
    assert briefing.center_messages[0].clinic_id == "clinic-b"


def test_briefing_rejects_unknown_center_reference():
    with pytest.raises(ValidationError, match="unknown clinic"):
        validate_situation_briefing(briefing_payload("invented-clinic"), {"clinic-b"})
