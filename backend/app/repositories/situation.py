from __future__ import annotations


class SituationRepository:
    """Read-only Neo4j access for bounded operational situation facts."""

    def __init__(self, client):
        self.client = client

    def load(self, cutoff: str):
        def work(tx):
            clinics = [
                dict(record["c"])
                for record in tx.run("MATCH (c:Clinic) RETURN c ORDER BY c.name")
            ]
            warehouses = [
                {**dict(record["w"]), "relevant_clinic_ids": list(record["target_ids"])}
                for record in tx.run(
                    """
                    MATCH (w:Warehouse)-[r:CAN_SUPPLY]->(c:Clinic)
                    WHERE c.risk_level IN ['high', 'critical']
                    RETURN w, collect(c.id) AS target_ids ORDER BY w.name
                    """
                )
            ]
            transfers = [
                dict(record["t"])
                for record in tx.run(
                    """
                    MATCH (t:Transfer)
                    WHERE t.status = 'ongoing' OR t.created_at >= $cutoff
                    RETURN t ORDER BY t.created_at DESC
                    """,
                    cutoff=cutoff,
                )
            ]
            observations = [
                dict(record["o"])
                for record in tx.run(
                    """
                    MATCH (o:Observation)
                    WHERE o.status = 'applied' AND o.created_at >= $cutoff
                    RETURN o ORDER BY o.created_at ASC
                    """,
                    cutoff=cutoff,
                )
            ]
            return clinics, warehouses, transfers, observations

        return self.client.read(work)
