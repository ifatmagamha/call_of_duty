from typing import Literal

from app.core.config import Settings


CrusoeTask = Literal["image", "audio", "situation"]


class ModelRouter:
    def __init__(self, settings: Settings):
        self._models = {
            "image": settings.crusoe_image_model,
            "audio": settings.crusoe_audio_model,
            "situation": settings.crusoe_situation_model,
        }

    def model_for(self, task: CrusoeTask | str) -> str:
        try:
            return self._models[task]
        except KeyError as exc:
            raise ValueError(f"Unknown Crusoe task: {task}") from exc
