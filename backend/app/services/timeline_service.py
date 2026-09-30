from __future__ import annotations

from typing import Any

from app.schemas import TimelineEntry
from app.infrastructure.neo4j.client import Neo4jClient
from app.services.observation_service import MUTATION_FIELDS


FIELD_LABELS = {
    "people_waiting": "People waiting",
    "test_kits_available": "Test kits",
    "nurses_available": "Nurses",
}


def observation_entry(node: dict[str, Any], clinic: dict[str, Any]) -> TimelineEntry:
    field = MUTATION_FIELDS.get(node["event_type"])
    status = node["status"]
    value = node.get(field) if field else None
    if field is None:
        title = node.get("status_note") or "Status reported"
    elif status == "applied" and node.get("previous_value") is not None:
        title = f"{FIELD_LABELS[field]} {node['previous_value']} → {value}"
    else:
        title = f"{FIELD_LABELS[field]} reported: {value}"
    return TimelineEntry(
        id=node["id"],
        kind="observation",
        clinic_id=clinic["id"],
        clinic_name=clinic["name"],
        at=node.get("reviewed_at") if status == "applied" and node.get("reviewed_at") else node["created_at"],
        title=title,
        detail=node.get("transcript") or node.get("evidence_summary") or "",
        status=status,
        source_type=node.get("source_type"),
        field=field,
        value=value if status == "applied" else None,
    )


def transfer_entries(
    transfer: dict[str, Any], source: dict[str, Any], clinic: dict[str, Any]
) -> list[TimelineEntry]:
    common = {"kind": "transfer", "clinic_id": clinic["id"], "clinic_name": clinic["name"]}
    entries = [
        TimelineEntry(
            **common,
            id=f"{transfer['id']}:dispatched",
            at=transfer["created_at"],
            title=f"{transfer['quantity']} kits dispatched from {source['name']}",
            detail=f"ETA {transfer['delivery_time_minutes']} min on a {transfer['road_status']} route.",
            status="ongoing" if transfer["status"] == "ongoing" else "dispatched",
        )
    ]
    if transfer["status"] == "completed":
        entries.append(
            TimelineEntry(
                **common,
                id=f"{transfer['id']}:completed",
                at=transfer.get("completed_at") or transfer["updated_at"],
                title=f"{transfer['quantity']} kits delivered from {source['name']}",
                detail="Clinic stock increased and risk recomputed.",
                status="completed",
            )
        )
    return entries


def get_timeline(
    client: Neo4jClient, clinic_id: str | None = None, limit: int = 50
) -> list[TimelineEntry]:
    def work(tx):
        observations = tx.run(
            """
            MATCH (o:Observation)-[:OBSERVED_AT]->(c:Clinic)
            WHERE $clinic_id IS NULL OR c.id = $clinic_id
            RETURN o, c ORDER BY o.created_at DESC LIMIT $limit
            """,
            clinic_id=clinic_id, limit=limit,
        )
        entries = [observation_entry(dict(r["o"]), dict(r["c"])) for r in observations]
        transfers = tx.run(
            """
            MATCH (s:Warehouse)-[:TRANSFER_SOURCE]->(t:Transfer)-[:TRANSFER_TARGET]->(c:Clinic)
            WHERE $clinic_id IS NULL OR c.id = $clinic_id
            RETURN t, s, c ORDER BY t.created_at DESC LIMIT $limit
            """,
            clinic_id=clinic_id, limit=limit,
        )
        for r in transfers:
            entries.extend(transfer_entries(dict(r["t"]), dict(r["s"]), dict(r["c"])))
        return entries

    entries = client.read(work)
    return sorted(entries, key=lambda entry: entry.at, reverse=True)[:limit]
