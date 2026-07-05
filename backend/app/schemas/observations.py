from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter


ObservationSourceType = Literal["image", "audio", "manual"]
ObservationStatus = Literal["pending_review", "applied", "rejected", "failed"]
NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ObservationCandidateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinic_id: NonBlankString
    source_type: ObservationSourceType
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime
    raw_text: NonBlankString | None = None
    transcript: NonBlankString | None = None
    evidence_summary: NonBlankString
    model_id: NonBlankString
    request_id: str | None = None


class QueueCountUpdated(ObservationCandidateBase):
    event_type: Literal["QUEUE_COUNT_UPDATED"]
    people_waiting: int = Field(ge=0)


class TestKitsUpdated(ObservationCandidateBase):
    event_type: Literal["TEST_KITS_UPDATED"]
    test_kits_available: int = Field(ge=0)


class NursesAvailableUpdated(ObservationCandidateBase):
    event_type: Literal["NURSES_AVAILABLE_UPDATED"]
    nurses_available: int = Field(ge=0)


class ClinicStatusReported(ObservationCandidateBase):
    event_type: Literal["CLINIC_STATUS_REPORTED"]
    status_note: NonBlankString


ObservationCandidate = Annotated[
    Union[
        QueueCountUpdated,
        TestKitsUpdated,
        NursesAvailableUpdated,
        ClinicStatusReported,
    ],
    Field(discriminator="event_type"),
]
observation_candidate_adapter = TypeAdapter(ObservationCandidate)


def validate_observation_candidate(value: object) -> ObservationCandidate:
    return observation_candidate_adapter.validate_python(value)


class Observation(BaseModel):
    id: str
    event: ObservationCandidate
    status: ObservationStatus
    previous_value: int | str | None = None
    new_value: int | str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    error_detail: str | None = None
    model_id: str
    request_id: str | None = None
    token_usage: dict[str, int] | None = None
