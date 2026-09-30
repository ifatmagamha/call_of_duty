from __future__ import annotations

from typing import Any


def fetch_clinic(tx, clinic_id: str) -> dict[str, Any] | None:
    """Transaction-level read, for callers composing a larger transaction."""
    record = tx.run("MATCH (c:Clinic {id: $clinic_id}) RETURN c", clinic_id=clinic_id).single()
    return dict(record["c"]) if record else None


def get_clinic(client, clinic_id: str) -> dict[str, Any] | None:
    return client.read(fetch_clinic, clinic_id=clinic_id)


def list_clinics(client) -> list[dict[str, Any]]:
    def work(tx):
        return [dict(record["c"]) for record in tx.run("MATCH (c:Clinic) RETURN c ORDER BY c.name")]

    return client.read(work)


def list_clinic_ids(client) -> list[str]:
    def work(tx):
        return [record["id"] for record in tx.run("MATCH (c:Clinic) RETURN c.id AS id")]

    return client.read(work)


def list_alert_clinics(client) -> list[dict[str, Any]]:
    """Clinics needing attention, most urgent first (shared by /alerts and /actions)."""

    def work(tx):
        result = tx.run(
            """
            MATCH (c:Clinic)
            WHERE c.risk_level IN ['critical', 'high']
               OR c.operations_remaining_hours < 2
               OR c.test_kits_available < c.threshold_min_kits
            RETURN c
            ORDER BY
              CASE c.risk_level
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                ELSE 3
              END,
              c.operations_remaining_hours ASC
            """
        )
        return [dict(record["c"]) for record in result]

    return client.read(work)
