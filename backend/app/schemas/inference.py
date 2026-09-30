from typing import Literal

from pydantic import BaseModel, Field

from .domain import AgentRecommendation, Clinic
from .observations import Observation, ObservationCandidate


class AudioExtraction(BaseModel):
    transcript: str
    event: ObservationCandidate


class ProviderMetadata(BaseModel):
    request_id: str | None = None
    token_usage: dict[str, int] | None = None


class ImageExtractionResult(BaseModel):
    event: ObservationCandidate
    metadata: ProviderMetadata


class AudioExtractionResult(BaseModel):
    extraction: AudioExtraction
    metadata: ProviderMetadata


class ImageIngestionResponse(BaseModel):
    observation: Observation
    clinic: Clinic | None = None
    recommendation: AgentRecommendation | None = None


class AudioIngestionResponse(ImageIngestionResponse):
    transcript: str


class VideoIngestionResponse(ImageIngestionResponse):
    sampled_frames: int
    duration_seconds: float


class TextReport(BaseModel):
    text: str = Field(min_length=1)
    clinic_hint: str | None = None
    channel: Literal["sms", "phone_transcript", "field_report", "other"] = "field_report"
