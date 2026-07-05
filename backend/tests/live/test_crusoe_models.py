import os
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import get_settings
from app.infrastructure.crusoe.client import CrusoeClient
from app.inference.agents import (
    AudioObservationAgent,
    ImageObservationAgent,
    SituationAgent,
)
from app.inference.media import MediaService


pytestmark = [
    pytest.mark.crusoe_live,
    pytest.mark.skipif(
        os.getenv("RUN_CRUSOE_LIVE") != "1" or not os.getenv("CRUSOE_API_KEY"),
        reason="requires RUN_CRUSOE_LIVE=1 and CRUSOE_API_KEY",
    ),
]


def image_fixture():
    stream = BytesIO()
    Image.new("RGB", (320, 120), "white").save(stream, "PNG")
    return MediaService().prepare_image(stream.getvalue(), "image/png")


def audio_fixture():
    audio = Path(__file__).resolve().parents[1] / "fixtures" / "clinic-b-kits.wav"
    return MediaService().prepare_audio(audio.read_bytes(), "audio/wav")


@pytest.mark.asyncio
async def test_all_three_crusoe_models_live_smoke():
    settings = get_settings()
    client = CrusoeClient(settings)
    image = await ImageObservationAgent(client, settings).extract(
        image_fixture(),
        ["clinic-b"],
        "clinic-b",
    )
    assert image.event.model_id == settings.crusoe_image_model

    audio = await AudioObservationAgent(client, settings).extract(
        audio_fixture(),
        ["clinic-b"],
        "clinic-b",
    )
    assert audio.extraction.event.model_id == settings.crusoe_audio_model
    assert audio.extraction.event.event_type == "TEST_KITS_UPDATED"
    assert audio.extraction.event.test_kits_available == 18

    briefing = await SituationAgent(client, settings).generate(
        {
            "clinics": [{"id": "clinic-b", "risk_level": "normal"}],
            "deterministic_trends": [],
            "source_observation_ids": [],
        }
    )
    assert briefing.model_id == settings.crusoe_situation_model
