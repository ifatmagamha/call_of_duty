from __future__ import annotations

from typing import Any

from app.schemas import Observation, ObservationCandidate, validate_observation_candidate
from app.services.observation_service import (
    MUTATION_FIELDS,
    UPDATE_QUERIES,
    event_mutation,
    updated_clinic_properties,
)
from app.services.risk_service import utc_now_iso


class Neo4jObservationRepository:
    def __init__(self, client):
        self.client = client

    @staticmethod
    def _event_from_node(node: dict[str, Any]) -> ObservationCandidate:
        common = {
            key: node.get(key)
            for key in (
                "event_type", "clinic_id", "source_type", "confidence",
                "observed_at", "raw_text", "transcript", "evidence_summary",
                "model_id", "request_id",
            )
            if node.get(key) is not None
        }
        field = MUTATION_FIELDS.get(node["event_type"])
        common[field if field else "status_note"] = node[field if field else "status_note"]
        return validate_observation_candidate(common)

    @classmethod
    def _from_node(cls, value: Any) -> Observation:
        node = dict(value)
        return Observation(
            id=node["id"], event=cls._event_from_node(node), status=node["status"],
            previous_value=node.get("previous_value"), new_value=node.get("new_value"),
            created_at=node["created_at"], reviewed_at=node.get("reviewed_at"),
            error_detail=node.get("error_detail"), model_id=node["model_id"],
            request_id=node.get("request_id"), token_usage=node.get("token_usage"),
        )

    def clinic_exists(self, clinic_id: str) -> bool:
        def work(tx):
            return tx.run(
                "MATCH (c:Clinic {id: $clinic_id}) RETURN count(c) > 0 AS exists",
                clinic_id=clinic_id,
            ).single()["exists"]
        return bool(self.client.read(work))

    def create(self, observation: Observation) -> tuple[Observation, bool]:
        existing = self.get(observation.id)
        if existing is not None:
            return existing, False
        props = {
            **observation.event.model_dump(mode="json", exclude_none=True),
            "id": observation.id, "status": observation.status,
            "created_at": observation.created_at.isoformat(),
            "model_id": observation.model_id, "request_id": observation.request_id,
            "error_detail": observation.error_detail,
        }
        def work(tx):
            record = tx.run(
                """
                MATCH (c:Clinic {id: $clinic_id})
                MERGE (o:Observation {id: $observation_id})
                ON CREATE SET o += $props
                MERGE (o)-[:OBSERVED_AT]->(c)
                RETURN o
                """,
                clinic_id=observation.event.clinic_id,
                observation_id=observation.id, props=props,
            ).single()
            return self._from_node(record["o"]) if record else None
        created = self.client.write(work)
        if created is None:
            raise ValueError("Clinic not found")
        return created, True

    def get(self, observation_id: str) -> Observation | None:
        def work(tx):
            record = tx.run(
                "MATCH (o:Observation {id: $observation_id}) RETURN o",
                observation_id=observation_id,
            ).single()
            return self._from_node(record["o"]) if record else None
        return self.client.read(work)

    def list(self, *, status=None, clinic_id=None, source_type=None, limit=100):
        def work(tx):
            result = tx.run(
                """
                MATCH (o:Observation)-[:OBSERVED_AT]->(c:Clinic)
                WHERE ($status IS NULL OR o.status = $status)
                  AND ($clinic_id IS NULL OR c.id = $clinic_id)
                  AND ($source_type IS NULL OR o.source_type = $source_type)
                RETURN o ORDER BY o.created_at DESC LIMIT $limit
                """,
                status=status, clinic_id=clinic_id, source_type=source_type, limit=limit,
            )
            return [self._from_node(record["o"]) for record in result]
        return self.client.read(work)

    def apply(self, observation_id: str) -> Observation | None:
        def work(tx):
            record = tx.run(
                "MATCH (o:Observation {id: $observation_id})-[:OBSERVED_AT]->(c:Clinic) RETURN o, c",
                observation_id=observation_id,
            ).single()
            if record is None:
                return None
            node = dict(record["o"])
            if node["status"] == "applied":
                return self._from_node(node)
            if node["status"] != "pending_review":
                raise ValueError(f"Observation is already {node['status']}")
            event = self._event_from_node(node)
            reviewed_at = utc_now_iso()
            mutation = event_mutation(event)
            if mutation is None:
                updated = tx.run(
                    """
                    MATCH (o:Observation {id: $observation_id})
                    SET o.status = 'applied', o.reviewed_at = $reviewed_at, o.error_detail = null
                    RETURN o
                    """,
                    observation_id=observation_id, reviewed_at=reviewed_at,
                ).single()
                return self._from_node(updated["o"])
            field, new_value = mutation
            clinic = dict(record["c"])
            props = updated_clinic_properties(clinic, event)
            updated = tx.run(
                UPDATE_QUERIES[event.event_type], observation_id=observation_id,
                previous_value=clinic[field], new_value=new_value,
                reviewed_at=reviewed_at, previous_risk_level=clinic.get("risk_level"),
                new_risk_level=props["risk_level"],
                metrics={key: value for key, value in props.items() if key != field},
            ).single()
            return self._from_node(updated["o"])
        return self.client.write(work)

    def reject(self, observation_id: str) -> Observation | None:
        def work(tx):
            record = tx.run(
                """
                MATCH (o:Observation {id: $observation_id}) WHERE o.status = 'pending_review'
                SET o.status = 'rejected', o.reviewed_at = $reviewed_at RETURN o
                """,
                observation_id=observation_id, reviewed_at=utc_now_iso(),
            ).single()
            if record:
                return self._from_node(record["o"])
            existing = tx.run(
                "MATCH (o:Observation {id: $observation_id}) RETURN o",
                observation_id=observation_id,
            ).single()
            if existing is None:
                return None
            raise ValueError(f"Observation is already {existing['o']['status']}")
        return self.client.write(work)


# Transitional name for callers that used the old service-local store.
Neo4jObservationStore = Neo4jObservationRepository
