import pytest

from app.core.config import Settings
from app.inference.model_router import ModelRouter


def test_exact_task_model_routing():
    router = ModelRouter(Settings(_env_file=None))
    assert router.model_for("image") == "google/gemma-4-31b-it"
    assert (
        router.model_for("audio")
        == "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"
    )
    assert router.model_for("situation") == "moonshotai/Kimi-K2.6"


def test_unknown_task_is_rejected():
    router = ModelRouter(Settings(_env_file=None))
    with pytest.raises(ValueError, match="Unknown Crusoe task"):
        router.model_for("transfer")
