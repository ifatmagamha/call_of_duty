from app.services.llm_agent import generate_critical_llm_note


def test_legacy_critical_note_is_cleanly_deprecated():
    assert generate_critical_llm_note({}, [], None) is None
