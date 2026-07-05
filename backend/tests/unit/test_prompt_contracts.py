from app.inference.agents import PROMPT_DIR


def test_audio_prompt_maps_explicit_numeric_facts_to_typed_events():
    prompt = (PROMPT_DIR / "audio_observation.md").read_text(encoding="utf-8")

    assert "TEST_KITS_UPDATED" in prompt
    assert "test_kits_available" in prompt
    assert "QUEUE_COUNT_UPDATED" in prompt
    assert "people_waiting" in prompt
    assert "NURSES_AVAILABLE_UPDATED" in prompt
    assert "nurses_available" in prompt
    assert "CLINIC_STATUS_REPORTED only when" in prompt
