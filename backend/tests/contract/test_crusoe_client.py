import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.infrastructure.crusoe.client import (
    CrusoeAuthenticationError,
    CrusoeClient,
    CrusoeUnavailableError,
    CrusoeUnknownModelError,
)


NOW = "2026-07-05T10:00:00+00:00"


def completion(payload, request_id="req-1"):
    return SimpleNamespace(
        id=request_id,
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
    )


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeOpenAI:
    def __init__(self, outcomes):
        self.completions = FakeCompletions(outcomes)
        self.chat = SimpleNamespace(completions=self.completions)


class StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"provider status {status_code}")
        self.status_code = status_code


def settings(**overrides):
    return Settings(crusoe_api_key="test-only", _env_file=None, **overrides)


def image_event():
    return {
        "event_type": "TEST_KITS_UPDATED",
        "clinic_id": "clinic-b",
        "source_type": "image",
        "confidence": 0.96,
        "observed_at": NOW,
        "evidence_summary": "Board shows twenty kits.",
        "model_id": "google/gemma-4-31b-it",
        "test_kits_available": 20,
    }


@pytest.mark.asyncio
async def test_gemma_valid_extraction_and_image_precedes_text():
    fake = FakeOpenAI([completion(image_event())])
    client = CrusoeClient(settings(), openai_client=fake)
    result = await client.extract_image("data:image/jpeg;base64,abc", "prompt")

    call = fake.completions.calls[0]
    assert call["model"] == "google/gemma-4-31b-it"
    content = call["messages"][0]["content"]
    assert content[0]["type"] == "image_url"
    assert content[1]["type"] == "text"
    assert call["response_format"]["type"] == "json_schema"
    assert result.event.test_kits_available == 20
    assert result.metadata.request_id == "req-1"


@pytest.mark.asyncio
async def test_gemma_malformed_json_fails_closed():
    fake = FakeOpenAI([completion(image_event())])
    fake.outcomes = []
    fake = FakeOpenAI(
        [SimpleNamespace(id="req", choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))], usage=None)]
    )
    with pytest.raises(ValidationError):
        await CrusoeClient(settings(), openai_client=fake).extract_image("data:image/jpeg;base64,a", "p")


@pytest.mark.asyncio
async def test_nemotron_transcript_event_and_thinking_disabled():
    payload = {"transcript": "Clinic B has twenty test kits remaining.", "event": image_event() | {"source_type": "audio", "model_id": "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"}}
    fake = FakeOpenAI([completion(payload)])
    result = await CrusoeClient(settings(), openai_client=fake).extract_audio(
        "data:audio/wav;base64,abc", "prompt"
    )
    call = fake.completions.calls[0]
    assert call["model"] == "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"
    audio_content = call["messages"][0]["content"][0]
    assert audio_content == {
        "type": "audio_url",
        "audio_url": {"url": "data:audio/wav;base64,abc"},
    }
    assert call["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert result.extraction.transcript.startswith("Clinic B")


@pytest.mark.asyncio
async def test_kimi_valid_briefing_and_thinking_disabled():
    payload = {
        "global_status": "watch", "headline": "Watch clinic B", "summary": "Queue pressure increased.",
        "detected_trends": ["queue increased"], "center_messages": [{"clinic_id": "clinic-b", "message": "Review queue."}],
        "recommended_operator_checks": ["Confirm report"], "generated_at": NOW,
        "model_id": "moonshotai/Kimi-K2.6", "source_observation_ids": ["obs-1"],
    }
    fake = FakeOpenAI([completion(payload)])
    briefing = await CrusoeClient(settings(), openai_client=fake).generate_briefing(
        {"clinics": [{"id": "clinic-b"}]}, "prompt", {"clinic-b"}
    )
    assert briefing.headline == "Watch clinic B"
    assert fake.completions.calls[0]["extra_body"] == {"chat_template_kwargs": {"thinking": False}}


@pytest.mark.asyncio
async def test_kimi_rejects_invalid_clinic_reference():
    payload = {
        "global_status": "watch", "headline": "Watch", "summary": "Summary",
        "detected_trends": [], "center_messages": [{"clinic_id": "made-up", "message": "No."}],
        "recommended_operator_checks": [], "generated_at": NOW,
        "model_id": "moonshotai/Kimi-K2.6", "source_observation_ids": [],
    }
    with pytest.raises(ValidationError, match="unknown clinic"):
        await CrusoeClient(settings(), openai_client=FakeOpenAI([completion(payload)])).generate_briefing({}, "p", {"clinic-b"})


@pytest.mark.asyncio
async def test_429_retries_but_auth_and_unknown_model_do_not():
    fake = FakeOpenAI([StatusError(429), completion(image_event())])
    await CrusoeClient(settings(crusoe_max_retries=1), openai_client=fake, sleep=lambda _: _done()).extract_image("data:image/jpeg;base64,a", "p")
    assert len(fake.completions.calls) == 2

    for status, error in [(401, CrusoeAuthenticationError), (403, CrusoeAuthenticationError), (404, CrusoeUnknownModelError)]:
        failed = FakeOpenAI([StatusError(status)])
        with pytest.raises(error):
            await CrusoeClient(settings(), openai_client=failed).extract_image("data:image/jpeg;base64,a", "p")
        assert len(failed.completions.calls) == 1


@pytest.mark.asyncio
async def test_412_unavailable_server_receives_bounded_retry():
    fake = FakeOpenAI([StatusError(412), completion(image_event())])
    await CrusoeClient(
        settings(crusoe_max_retries=1),
        openai_client=fake,
        sleep=lambda _: _done(),
    ).extract_image("data:image/jpeg;base64,a", "p")

    assert len(fake.completions.calls) == 2


async def _done():
    return None


@pytest.mark.asyncio
async def test_timeout_and_missing_api_key_are_safe():
    with pytest.raises(CrusoeUnavailableError, match="timed out"):
        await CrusoeClient(settings(), openai_client=FakeOpenAI([TimeoutError()])).extract_image("data:image/jpeg;base64,a", "p")
    with pytest.raises(CrusoeUnavailableError, match="not configured"):
        await CrusoeClient(Settings(_env_file=None), openai_client=FakeOpenAI([])).extract_image("data:image/jpeg;base64,a", "p")
