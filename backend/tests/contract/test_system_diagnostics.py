from types import SimpleNamespace

import pytest

from app.core.config import Settings


class FakeNeo4jClient:
    database = "neo4j"

    def verify_connectivity(self):
        return None

    def read(self, work, **kwargs):
        return work(FakeTx(), **kwargs)


class FakeResult(list):
    def single(self):
        return self[0] if self else None


class FakeTx:
    def run(self, query, **kwargs):
        if "SHOW CONSTRAINTS" in query:
            return FakeResult(
                [
                    {"name": "clinic_id"},
                    {"name": "warehouse_id"},
                    {"name": "observation_id"},
                ]
            )
        if "labels(n)" in query:
            return FakeResult(
                [
                    {"label": "Clinic", "count": 5},
                    {"label": "Warehouse", "count": 3},
                    {"label": "Observation", "count": 2},
                ]
            )
        if "OBSERVED_AT" in query:
            return FakeResult([{"count": 2}])
        raise AssertionError(query)


class FakeModels:
    async def list(self):
        return SimpleNamespace(
            data=[
                SimpleNamespace(id="google/gemma-4-31b-it"),
                SimpleNamespace(id="nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"),
                SimpleNamespace(id="moonshotai/Kimi-K2.6"),
            ]
        )


class FakeOpenAI:
    models = FakeModels()


class FailingModels:
    async def list(self):
        raise RuntimeError("provider body must not escape")


class FailingOpenAI:
    models = FailingModels()


def test_neo4j_diagnostic_proves_graph_shape_and_query_access():
    from app.services.system_diagnostics import SystemDiagnostics

    result = SystemDiagnostics(
        Settings(_env_file=None), neo4j_client=FakeNeo4jClient()
    ).check_neo4j()

    assert result.connected is True
    assert result.required_constraints_present is True
    assert result.node_counts == {"Clinic": 5, "Warehouse": 3, "Observation": 2}
    assert result.observation_links == 2


@pytest.mark.asyncio
async def test_crusoe_diagnostic_proves_all_configured_models_are_accessible():
    from app.infrastructure.crusoe.client import CrusoeClient
    from app.services.system_diagnostics import SystemDiagnostics

    settings = Settings(crusoe_api_key="test-only", _env_file=None)
    client = CrusoeClient(settings, openai_client=FakeOpenAI())
    result = await SystemDiagnostics(settings, crusoe_client=client).check_crusoe()

    assert result.configured is True
    assert result.all_models_accessible is True
    assert result.missing_model_ids == []
    assert set(result.required_model_ids) == {
        settings.crusoe_image_model,
        settings.crusoe_audio_model,
        settings.crusoe_situation_model,
    }


@pytest.mark.asyncio
async def test_crusoe_diagnostic_reports_missing_model_without_exposing_key():
    from app.infrastructure.crusoe.client import CrusoeClient
    from app.services.system_diagnostics import SystemDiagnostics

    settings = Settings(
        crusoe_api_key="do-not-expose",
        crusoe_situation_model="missing/model",
        _env_file=None,
    )
    client = CrusoeClient(settings, openai_client=FakeOpenAI())
    result = await SystemDiagnostics(settings, crusoe_client=client).check_crusoe()

    assert result.all_models_accessible is False
    assert result.missing_model_ids == ["missing/model"]
    assert "do-not-expose" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_crusoe_diagnostic_maps_provider_failure_to_safe_result():
    from app.infrastructure.crusoe.client import CrusoeClient
    from app.services.system_diagnostics import SystemDiagnostics

    settings = Settings(crusoe_api_key="never-print-this", _env_file=None)
    client = CrusoeClient(settings, openai_client=FailingOpenAI())
    result = await SystemDiagnostics(settings, crusoe_client=client).check_crusoe()

    assert result.all_models_accessible is False
    serialized = result.model_dump_json()
    assert "never-print-this" not in serialized
    assert "provider body" not in serialized
