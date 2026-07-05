import pytest

from app.core.config import Settings
from app.schemas import SituationBriefing
from app.inference.situation_agent import SituationAgent


class FakeClient:
    async def generate_briefing(self, snapshot, prompt, valid_ids):
        return SituationBriefing(
            global_status="watch",
            headline="Watch",
            summary="Summary",
            detected_trends=["invented trend"],
            center_messages=[],
            recommended_operator_checks=[],
            generated_at="2026-07-05T10:00:00+00:00",
            model_id="moonshotai/Kimi-K2.6",
            source_observation_ids=[],
        )


class UntrustedProvenanceClient:
    async def generate_briefing(self, snapshot, prompt, valid_ids):
        return SituationBriefing(
            global_status="stable",
            headline="Stable",
            summary="No deterministic trend was supplied.",
            detected_trends=[],
            center_messages=[],
            recommended_operator_checks=[],
            generated_at="2026-07-05T10:00:00+00:00",
            model_id="provider-invented-model",
            source_observation_ids=["provider-invented-observation"],
        )


@pytest.mark.asyncio
async def test_situation_agent_rejects_invented_trends():
    snapshot = {
        "clinics": [{"id": "clinic-b"}],
        "deterministic_trends": ["clinic-b queue increased from 80 to 96"],
    }
    with pytest.raises(ValueError, match="non-deterministic trend"):
        await SituationAgent(FakeClient(), Settings(_env_file=None)).generate(snapshot)


@pytest.mark.asyncio
async def test_situation_agent_replaces_untrusted_provenance():
    snapshot = {
        "clinics": [{"id": "clinic-b"}],
        "deterministic_trends": [],
        "source_observation_ids": ["obs-trusted"],
    }
    settings = Settings(_env_file=None)

    briefing = await SituationAgent(
        UntrustedProvenanceClient(), settings
    ).generate(snapshot)

    assert briefing.model_id == settings.crusoe_situation_model
    assert briefing.source_observation_ids == ["obs-trusted"]
