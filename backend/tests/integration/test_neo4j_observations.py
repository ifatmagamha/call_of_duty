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
