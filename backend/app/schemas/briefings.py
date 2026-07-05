from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator


class CenterMessage(BaseModel):
    clinic_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class SituationBriefing(BaseModel):
    global_status: Literal["stable", "watch", "degrading", "critical"]
    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    detected_trends: list[str]
    center_messages: list[CenterMessage]
    recommended_operator_checks: list[str]
    generated_at: datetime
    model_id: str
    source_observation_ids: list[str]

    @model_validator(mode="after")
    def known_center_references(self, info: ValidationInfo):
        valid_ids = (info.context or {}).get("valid_clinic_ids")
        if valid_ids is None:
            return self
        unknown = {
            item.clinic_id for item in self.center_messages if item.clinic_id not in valid_ids
        }
        if unknown:
            raise ValueError(f"center message references unknown clinic: {sorted(unknown)}")
        return self


def validate_situation_briefing(
    value: object, valid_clinic_ids: set[str]
) -> SituationBriefing:
    return SituationBriefing.model_validate(
        value, context={"valid_clinic_ids": valid_clinic_ids}
    )


class BriefingGenerateRequest(BaseModel):
    window_hours: int = Field(default=24, ge=1, le=168)
