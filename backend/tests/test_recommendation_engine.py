from app.services.recommendation_engine import (
    get_agent_recommendation,
    get_resupply_options,
)


class FakeRecord(dict):
    def single(self):
        return self


class FakeResult(list):
    def single(self):
        return self[0] if self else None


class FakeTx:
    def __init__(self, clinic):
        self.clinic = clinic
        self.queries = []

    def run(self, query, **kwargs):
        self.queries.append(query)
        if "MATCH (c:Clinic" in query:
            return FakeRecord({"c": self.clinic})

        assert "MATCH (source:Warehouse)-[route:CAN_SUPPLY]" in query
        return FakeResult(
            [
                FakeRecord(
                    {
                        "source": {
                            "id": "warehouse-w1",
                            "name": "Central Medical Warehouse",
                            "test_kits_stock": 1000,
                        },
                        "route": {
                            "delivery_time_minutes": 25,
                            "road_status": "open",
                        },
                    }
                )
            ]
        )


class FakeClient:
    def __init__(self, clinic):
        self.tx = FakeTx(clinic)

    def read(self, work, **kwargs):
        return work(self.tx, **kwargs)


def test_resupply_options_only_query_warehouses():
    client = FakeClient(
        {
            "id": "clinic-b",
            "name": "Lingwala Screening Center",
            "test_kits_available": 35,
            "people_waiting": 96,
            "nurses_available": 2,
            "threshold_min_kits": 50,
            "testing_capacity_per_hour": 24,
            "queue_delay_hours": 4.0,
            "operations_remaining_hours": 1.46,
            "risk_level": "high",
        }
    )

    options = get_resupply_options(client, "clinic-b")

    assert options[0].source_type == "warehouse"
    assert options[0].recommended_transfer_quantity == 61
    assert "another clinic's stock" in options[0].reason


def test_agent_does_not_propose_resupply_for_normal_clinic():
    client = FakeClient(
        {
            "id": "clinic-a",
            "name": "Gombe Response Center",
            "test_kits_available": 120,
            "people_waiting": 30,
            "nurses_available": 3,
            "threshold_min_kits": 50,
            "testing_capacity_per_hour": 36,
            "queue_delay_hours": 0.83,
            "operations_remaining_hours": 3.33,
            "risk_level": "normal",
        }
    )

    recommendation = get_agent_recommendation(client, "clinic-a")

    assert recommendation.llm_used is False
    assert recommendation.llm_agent is None
    assert recommendation.recommendation.startswith("No immediate")
    assert "warehouse_only" in recommendation.data_sources[-1]


def test_agent_adds_llm_note_for_critical_clinic_without_changing_deterministic_recommendation(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    client = FakeClient(
        {
            "id": "clinic-critical",
            "name": "Critical Clinic",
            "test_kits_available": 0,
            "people_waiting": 96,
            "nurses_available": 2,
            "threshold_min_kits": 50,
            "testing_capacity_per_hour": 24,
            "queue_delay_hours": 4.0,
            "operations_remaining_hours": 0.0,
            "risk_level": "critical",
        }
    )

    recommendation = get_agent_recommendation(client, "clinic-critical")

    assert recommendation.recommendation.startswith("Resupply")
    assert recommendation.llm_provider == "deterministic"
    assert recommendation.llm_agent is not None
    assert recommendation.llm_agent.available is False
