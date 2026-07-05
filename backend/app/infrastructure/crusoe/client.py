from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings
from app.schemas import (
    AudioExtraction,
    AudioExtractionResult,
    ImageExtractionResult,
    ProviderMetadata,
    SituationBriefing,
    validate_observation_candidate,
    validate_situation_briefing,
)
from app.schemas.observations import observation_candidate_adapter
from app.inference.model_router import CrusoeTask, ModelRouter


class CrusoeError(RuntimeError):
    """Safe base error; provider response bodies must not cross this boundary."""


class CrusoeUnavailableError(CrusoeError):
    pass


class CrusoeAuthenticationError(CrusoeError):
    pass


class CrusoeUnknownModelError(CrusoeError):
    pass


class CrusoeClient:
    def __init__(
        self,
        settings: Settings,
        *,
        openai_client: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.settings = settings
        self.router = ModelRouter(settings)
        self._sleep = sleep
        self._client = openai_client

    def _require_client(self):
        if not self.settings.crusoe_api_key:
            raise CrusoeUnavailableError("Crusoe inference is not configured.")
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.crusoe_api_key,
                base_url=self.settings.crusoe_base_url,
                timeout=self.settings.crusoe_timeout_seconds,
                max_retries=0,
            )
        return self._client

    @staticmethod
    def _status_code(exc: BaseException) -> int | None:
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        return status

    async def _create(
        self,
        task: CrusoeTask,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        *,
        extra_body: dict[str, Any] | None = None,
    ):
        client = self._require_client()
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": f"{task}_response",
                "strict": True,
                "schema": schema,
            },
        }
        used_json_object_fallback = False
        transient_attempt = 0
        while True:
            kwargs: dict[str, Any] = {
                "model": self.router.model_for(task),
                "messages": messages,
                "temperature": 0,
                "response_format": response_format,
            }
            if extra_body is not None:
                kwargs["extra_body"] = extra_body
            try:
                return await client.chat.completions.create(**kwargs)
            except TimeoutError as exc:
                raise CrusoeUnavailableError("Crusoe request timed out.") from exc
            except Exception as exc:
                status = self._status_code(exc)
                if status in {401, 403}:
                    raise CrusoeAuthenticationError(
                        "Crusoe rejected the configured credentials."
                    ) from exc
                if status == 404:
                    raise CrusoeUnknownModelError(
                        "The configured Crusoe model is unavailable."
                    ) from exc
                if status == 400 and not used_json_object_fallback:
                    response_format = {"type": "json_object"}
                    used_json_object_fallback = True
                    continue
                transient = status in {412, 429} or (
                    status is not None and status >= 500
                )
                if transient and transient_attempt < self.settings.crusoe_max_retries:
                    transient_attempt += 1
                    await self._sleep(min(2 ** (transient_attempt - 1), 4))
                    continue
                raise CrusoeUnavailableError("Crusoe inference is unavailable.") from exc

    @staticmethod
    def _content(completion: Any) -> str:
        content = completion.choices[0].message.content
        if not isinstance(content, str):
            raise CrusoeUnavailableError("Crusoe returned an empty response.")
        return content

    @staticmethod
    def _metadata(completion: Any) -> ProviderMetadata:
        usage = getattr(completion, "usage", None)
        token_usage = None
        if usage is not None:
            token_usage = {
                key: value
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if isinstance((value := getattr(usage, key, None)), int)
            }
        return ProviderMetadata(
            request_id=getattr(completion, "id", None),
            token_usage=token_usage or None,
        )

    async def extract_image(self, image_data_url: str, prompt: str) -> ImageExtractionResult:
        completion = await self._create(
            "image",
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            observation_candidate_adapter.json_schema(),
        )
        event = observation_candidate_adapter.validate_json(self._content(completion))
        return ImageExtractionResult(event=event, metadata=self._metadata(completion))

    async def extract_audio(self, audio_data_url: str, prompt: str) -> AudioExtractionResult:
        completion = await self._create(
            "audio",
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "audio_url",
                            "audio_url": {"url": audio_data_url},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            AudioExtraction.model_json_schema(),
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        extraction = AudioExtraction.model_validate_json(self._content(completion))
        return AudioExtractionResult(
            extraction=extraction, metadata=self._metadata(completion)
        )

    async def generate_briefing(
        self,
        snapshot: dict[str, Any],
        prompt: str,
        valid_clinic_ids: set[str],
    ) -> SituationBriefing:
        completion = await self._create(
            "situation",
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(snapshot, separators=(",", ":"))},
            ],
            SituationBriefing.model_json_schema(),
            extra_body={"chat_template_kwargs": {"thinking": False}},
        )
        return validate_situation_briefing(
            json.loads(self._content(completion)), valid_clinic_ids
        )

    async def list_models(self) -> list[str]:
        client = self._require_client()
        response = await client.models.list()
        return [item.id for item in response.data]
