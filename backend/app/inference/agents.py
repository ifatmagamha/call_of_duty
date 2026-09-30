from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _prompt(name: str, known_clinic_ids: list[str], clinic_hint: str | None) -> str:
    base = (PROMPT_DIR / name).read_text(encoding="utf-8")
    hint = clinic_hint if clinic_hint else "none"
    return f"{base}\nKNOWN_CLINIC_IDS: {known_clinic_ids}\nCLINIC_HINT: {hint}"


class ImageObservationAgent:
    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings

    async def extract(
        self, image_data_url: str, known_clinic_ids: list[str], clinic_hint: str | None
    ):
        result = await self.client.extract_image(
            image_data_url,
            _prompt("image_observation.md", known_clinic_ids, clinic_hint),
        )
        result.event = result.event.model_copy(
            update={
                "source_type": "image",
                "model_id": self.settings.crusoe_image_model,
                "request_id": result.metadata.request_id,
            }
        )
        return result


class AudioObservationAgent:
    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings

    async def extract(
        self, audio_data_url: str, known_clinic_ids: list[str], clinic_hint: str | None
    ):
        result = await self.client.extract_audio(
            audio_data_url,
            _prompt("audio_observation.md", known_clinic_ids, clinic_hint),
        )
        result.extraction.event = result.extraction.event.model_copy(
            update={
                "source_type": "audio",
                "model_id": self.settings.crusoe_audio_model,
                "request_id": result.metadata.request_id,
                "transcript": result.extraction.transcript,
            }
        )
        return result


class TextObservationAgent:
    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings

    async def extract(
        self, report: str, channel: str, known_clinic_ids: list[str], clinic_hint: str | None
    ):
        result = await self.client.extract_text(
            f"CHANNEL: {channel}\nREPORT:\n{report}",
            _prompt("text_observation.md", known_clinic_ids, clinic_hint),
        )
        result.event = result.event.model_copy(
            update={
                "source_type": "text",
                "model_id": self.settings.crusoe_text_model,
                "request_id": result.metadata.request_id,
                "raw_text": report,
            }
        )
        return result


class VideoObservationAgent:
    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings

    async def extract(
        self, contact_sheet_url: str, known_clinic_ids: list[str], clinic_hint: str | None
    ):
        result = await self.client.extract_image(
            contact_sheet_url,
            _prompt("video_observation.md", known_clinic_ids, clinic_hint),
        )
        result.event = result.event.model_copy(
            update={
                "source_type": "video",
                "model_id": self.settings.crusoe_image_model,
                "request_id": result.metadata.request_id,
            }
        )
        return result


class SituationAgent:
    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings

    async def generate(self, snapshot):
        valid_ids = {clinic["id"] for clinic in snapshot["clinics"]}
        prompt = (PROMPT_DIR / "situation_briefing.md").read_text(encoding="utf-8")
        briefing = await self.client.generate_briefing(snapshot, prompt, valid_ids)
        allowed_trends = set(snapshot["deterministic_trends"])
        invented = [trend for trend in briefing.detected_trends if trend not in allowed_trends]
        if invented:
            raise ValueError("Situation briefing contains a non-deterministic trend")
        return briefing.model_copy(
            update={
                "model_id": self.settings.crusoe_situation_model,
                "source_observation_ids": snapshot["source_observation_ids"],
            }
        )

    async def answer(self, snapshot, question: str):
        valid_ids = {clinic["id"] for clinic in snapshot["clinics"]}
        prompt = (PROMPT_DIR / "situation_question.md").read_text(encoding="utf-8")
        answer = await self.client.answer_question(snapshot, question, prompt, valid_ids)
        return answer.model_copy(update={"model_id": self.settings.crusoe_situation_model})
