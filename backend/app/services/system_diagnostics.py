from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.crusoe.client import CrusoeClient
from app.schemas import CrusoeDiagnostic, Neo4jDiagnostic


REQUIRED_CONSTRAINTS = ["clinic_id", "warehouse_id", "observation_id"]


class SystemDiagnostics:
    def __init__(
        self,
        settings: Settings,
        *,
        neo4j_client=None,
        crusoe_client: CrusoeClient | None = None,
    ):
        self.settings = settings
        self.neo4j_client = neo4j_client
        self.crusoe_client = crusoe_client

    def check_neo4j(self) -> Neo4jDiagnostic:
        if self.neo4j_client is None:
            return Neo4jDiagnostic(
                connected=False,
                database=self.settings.neo4j_database,
                required_constraints=REQUIRED_CONSTRAINTS,
                missing_constraints=REQUIRED_CONSTRAINTS,
                required_constraints_present=False,
                error="Neo4j client was not supplied.",
            )
        try:
            self.neo4j_client.verify_connectivity()

            def work(tx):
                constraints = [
                    record["name"]
                    for record in tx.run("SHOW CONSTRAINTS YIELD name RETURN name")
                ]
                counts = {
                    record["label"]: record["count"]
                    for record in tx.run(
                        """
                        MATCH (n)
                        UNWIND labels(n) AS label
                        RETURN label, count(n) AS count ORDER BY label
                        """
                    )
                }
                links = tx.run(
                    """
                    MATCH (:Observation)-[r:OBSERVED_AT]->(:Clinic)
                    RETURN count(r) AS count
                    """
                ).single()["count"]
                return constraints, counts, links

            constraints, counts, links = self.neo4j_client.read(work)
            missing = sorted(set(REQUIRED_CONSTRAINTS) - set(constraints))
            return Neo4jDiagnostic(
                connected=True,
                database=getattr(
                    self.neo4j_client, "database", self.settings.neo4j_database
                ),
                constraints=sorted(constraints),
                required_constraints=REQUIRED_CONSTRAINTS,
                missing_constraints=missing,
                required_constraints_present=not missing,
                node_counts=counts,
                observation_links=links,
            )
        except Exception:
            return Neo4jDiagnostic(
                connected=False,
                database=self.settings.neo4j_database,
                required_constraints=REQUIRED_CONSTRAINTS,
                missing_constraints=REQUIRED_CONSTRAINTS,
                required_constraints_present=False,
                error="Neo4j diagnostic failed. Check connectivity and credentials.",
            )

    async def check_crusoe(self) -> CrusoeDiagnostic:
        required = [
            self.settings.crusoe_image_model,
            self.settings.crusoe_audio_model,
            self.settings.crusoe_situation_model,
        ]
        if not self.settings.crusoe_api_key:
            return CrusoeDiagnostic(
                configured=False,
                required_model_ids=required,
                missing_model_ids=required,
                all_models_accessible=False,
                error="Crusoe inference is not configured.",
            )
        client = self.crusoe_client or CrusoeClient(self.settings)
        try:
            accessible = await client.list_models()
            missing = [model_id for model_id in required if model_id not in accessible]
            return CrusoeDiagnostic(
                configured=True,
                required_model_ids=required,
                accessible_model_ids=sorted(accessible),
                missing_model_ids=missing,
                all_models_accessible=not missing,
            )
        except Exception:
            return CrusoeDiagnostic(
                configured=True,
                required_model_ids=required,
                missing_model_ids=required,
                all_models_accessible=False,
                error="Crusoe model access check failed.",
            )
