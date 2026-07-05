from app.core.config import Settings


def test_crusoe_settings_have_exact_safe_defaults():
    settings = Settings(
        neo4j_password="password",
        _env_file=None,
    )

    assert settings.crusoe_base_url == "https://api.inference.crusoecloud.com/v1/"
    assert settings.crusoe_image_model == "google/gemma-4-31b-it"
    assert (
        settings.crusoe_audio_model
        == "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"
    )
    assert settings.crusoe_situation_model == "moonshotai/Kimi-K2.6"
    assert settings.observation_auto_apply_confidence == 0.90
    assert settings.neo4j_database == "neo4j"


def test_application_can_start_without_crusoe_key():
    settings = Settings(neo4j_password="password", _env_file=None)
    assert settings.crusoe_api_key == ""
