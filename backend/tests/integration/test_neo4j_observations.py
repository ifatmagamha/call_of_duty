import os
from datetime import datetime, timezone

import pytest

from app.infrastructure.neo4j.client import Neo4jClient
from app.repositories.observations import Neo4jObservationRepository
from app.services.observation_service import ObservationService
from app.demo.seed import seed_demo_graph
from app.schemas import validate_observation_candidate


pytestmark = [
    pytest.mark.neo4j_integration,
    pytest.mark.skipif(
        os.getenv("RUN_NEO4J_INTEGRATION") != "1",
        reason="set RUN_NEO4J_INTEGRATION=1 for destructive local graph integration tests",
    ),
]


def event(event_type, confidence, **value):
    return validate_observation_candidate(
        {
            "event_type": event_type,
            "clinic_id": "clinic-b",
            "source_type": "manual",
            "confidence": confidence,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence_summary": "Integration fixture",
            "model_id": "fixture",
            **value,
        }
    )


def test_observation_persistence_relationship_review_audit_and_recomputation():
    client = Neo4jClient()
    try:
        seed_demo_graph(client)
        service = ObservationService(Neo4jObservationRepository(client), 0.90)
        applied = service.process(
            event("TEST_KITS_UPDATED", 0.95, test_kits_available=20),
            observation_id="integration-auto",
        )
        pending = service.process(
            event("QUEUE_COUNT_UPDATED", 0.50, people_waiting=110),
            observation_id="integration-pending",
        )
        rejected = service.process(
            event("NURSES_AVAILABLE_UPDATED", 0.50, nurses_available=1),
            observation_id="integration-reject",
        )
        service.apply(pending.id)
        service.reject(rejected.id)
        duplicate = service.process(
            event("TEST_KITS_UPDATED", 0.95, test_kits_available=1),
            observation_id="integration-auto",
        )

        def inspect(tx):
            return tx.run(
                """
                MATCH (o:Observation {id: 'integration-auto'})-[:OBSERVED_AT]->(c:Clinic)
                RETURN o, c
                """
            ).single()

        record = client.read(inspect)
        assert applied.status == duplicate.status == "applied"
        assert applied.previous_value == 35 and applied.new_value == 20
        assert dict(record["c"])["test_kits_available"] == 20
        assert dict(record["c"])["risk_level"] == "critical"
        assert service.store.get("integration-pending").status == "applied"
        assert service.store.get("integration-reject").status == "rejected"
    finally:
        client.close()


def test_mvp_loop_camera_manual_dispatch_delivery_timeline_and_actions():
    from fastapi.testclient import TestClient

    from app.main import app

    client = Neo4jClient()
    try:
        seed_demo_graph(client)
        api = TestClient(app)

        actions = api.get("/actions").json()
        assert actions[0]["status"] in {"critical", "high"}
        assert {a["clinic_id"] for a in actions} >= {"clinic-b", "clinic-d"}

        camera = api.post(
            "/ingestion/camera",
            json={"clinic_id": "clinic-b", "camera_id": "cam-b", "people_count": 130},
        ).json()
        assert camera["status"] == "applied" and camera["previous_value"] == 96

        clinic = api.patch("/clinics/clinic-b", json={"nurses_available": 3}).json()
        assert clinic["nurses_available"] == 3 and clinic["people_waiting"] == 130

        transfer = api.post("/clinics/clinic-b/transfers", json={"source_id": "warehouse-w1"}).json()
        delivered = api.post(f"/transfers/{transfer['id']}/complete").json()
        assert delivered["status"] == "completed"
        assert api.post(f"/transfers/{transfer['id']}/complete").status_code == 409
        after = api.get("/clinics/clinic-b").json()
        assert after["test_kits_available"] == 35 + transfer["quantity"]

        timeline = api.get("/clinics/clinic-b/timeline").json()
        titles = [entry["title"] for entry in timeline]
        assert titles[0].endswith("kits delivered from Central Medical Warehouse")
        assert "People waiting 96 → 130" in titles
        assert "Nurses 2 → 3" in titles
        assert any(entry["source_type"] == "manual" for entry in timeline)
        assert api.get("/timeline").json()[0]["clinic_id"] == "clinic-b"
    finally:
        client.close()
