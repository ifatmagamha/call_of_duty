import asyncio
import os
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import get_settings
from app.infrastructure.crusoe.client import CrusoeClient
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


@pytest.mark.asyncio
async def test_all_three_crusoe_models_live_smoke():
    settings = get_settings()
    client = CrusoeClient(settings)
    image = await client.extract_image(
        image_fixture(),
        "Return a CLINIC_STATUS_REPORTED observation for clinic-b using the required JSON contract.",
    )
    assert image.event.model_id == settings.crusoe_image_model

    # Small valid WAV data URL; silence should produce a non-mutating status event.
    wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00@\x1f\x00\x00@\x1f\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00"
    audio = await client.extract_audio(
        MediaService().prepare_audio(wav, "audio/wav"),
        "Transcribe and return a CLINIC_STATUS_REPORTED event for clinic-b when no numeric fact is audible.",
    )
    assert audio.extraction.event.model_id == settings.crusoe_audio_model

    briefing = await client.generate_briefing(
        {"clinics": [{"id": "clinic-b", "risk_level": "normal"}], "deterministic_trends": [], "source_observation_ids": []},
        "Return a stable briefing with no trends and only clinic-b references.",
        {"clinic-b"},
    )
    assert briefing.model_id == settings.crusoe_situation_model
